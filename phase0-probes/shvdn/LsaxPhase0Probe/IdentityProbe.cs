// =====================================================================================
// DISPOSABLE PHASE 0 FEASIBILITY PROBE — NOT LSAX PRODUCTION CODE. DO NOT SHIP OR REUSE.
// P-ID-01: decorator survival and handle behaviour for a player vehicle.
// Opt-in: probe.ini IdentityProbe.Enabled=true. Registers ONE decorator "lsax_p0_tag" (int) and sets it on
// the player's current vehicle when TagKey is pressed. Observes, at 1 Hz and within a bounded radius,
// whether the tag is still present after stream-out/in, garage store/retrieve, save/load, impound.
// =====================================================================================
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using System.Windows.Forms;
using GTA;
using GTA.Native;

namespace LsaxPhase0Probe
{
    public sealed class IdentityProbe : Script
    {
        private const string Decor = "lsax_p0_tag";
        private const int DecorTypeInt = 3; // eDecorType.DECOR_TYPE_INT (native DB comment on DECOR_REGISTER)
        private const float ScanRadius = 120f;
        private const int MaxScan = 64;

        private readonly bool _enabled;
        private readonly Keys _tagKey;
        private readonly Dictionary<string, TagRecord> _tags = new Dictionary<string, TagRecord>(StringComparer.Ordinal); // key = plate|model
        private int _lastPlayerVehHandle;
        private string _lastPlayerVehDesc = string.Empty;
        private DateTime _nextScanUtc;

        public IdentityProbe()
        {
            _enabled = ProbeEnv.CfgBool("IdentityProbe.Enabled");
            Keys k;
            _tagKey = Enum.TryParse(ProbeEnv.Cfg("IdentityProbe.TagKey", "F10"), true, out k) ? k : Keys.F10;
            if (!_enabled)
            {
                ProbeEnv.Log("IDENTITY_DISABLED", "set IdentityProbe.Enabled=true");
                return;
            }

            Interval = 250;
            ProbeEnv.Log("IDENTITY_DECOR_REGISTERED_AT_START", Nat.B(Function.Call<bool>(Hash.DECOR_IS_REGISTERED_AS_TYPE, Decor, DecorTypeInt)));
            Tick += OnTick;
            KeyDown += OnKeyDown;
        }

        private void OnKeyDown(object sender, KeyEventArgs e)
        {
            if (e.KeyCode != _tagKey)
            {
                return;
            }

            try
            {
                Vehicle v = Game.Player.Character.CurrentVehicle;
                if (v == null || !v.Exists())
                {
                    ProbeEnv.Log("IDENTITY_TAG_NOVEHICLE", string.Empty);
                    return;
                }

                bool registered = EnsureRegistered();
                int token = Environment.TickCount & 0x7FFFFFFF;
                bool setOk = registered && Function.Call<bool>(Hash.DECOR_SET_INT, v, Decor, token);
                string key = Describe(v).Key;
                _tags[key] = new TagRecord { Token = token, LastHandle = v.Handle, Present = true };
                ProbeEnv.Log("IDENTITY_TAG", string.Format(CultureInfo.InvariantCulture, "registered={0} setOk={1} token={2} {3}",
                    Nat.B(registered), Nat.B(setOk), token, Describe(v).Text));
                GTA.UI.Notification.Show("LSAX P0 probe: vehicle tagged " + token.ToString(CultureInfo.InvariantCulture));
            }
            catch (Exception ex)
            {
                ProbeEnv.Log("PROBE_ERROR", "IdentityProbe tag: " + ex.GetType().Name + ": " + ex.Message);
            }
        }

        private void OnTick(object sender, EventArgs e)
        {
            try
            {
                Vehicle pv = Game.Player.Character.CurrentVehicle;
                int h = pv != null && pv.Exists() ? pv.Handle : 0;
                if (h != _lastPlayerVehHandle)
                {
                    string desc = h != 0 ? Describe(pv).Text : "<none>";
                    bool oldExists = _lastPlayerVehHandle != 0 && Function.Call<bool>(Hash.DOES_ENTITY_EXIST, _lastPlayerVehHandle);
                    ProbeEnv.Log("PLAYER_VEHICLE_CHANGED", string.Format(CultureInfo.InvariantCulture,
                        "oldHandle={0} oldStillExists={1} old=[{2}] new=[{3}]", _lastPlayerVehHandle, Nat.B(oldExists), _lastPlayerVehDesc, desc));
                    _lastPlayerVehHandle = h;
                    _lastPlayerVehDesc = desc;
                }

                if (_tags.Count == 0 || DateTime.UtcNow < _nextScanUtc)
                {
                    return;
                }

                _nextScanUtc = DateTime.UtcNow.AddSeconds(1);
                var seen = new HashSet<string>(StringComparer.Ordinal);
                Vehicle[] near = World.GetNearbyVehicles(Game.Player.Character.Position, ScanRadius);
                for (int i = 0; i < near.Length && i < MaxScan; i++)
                {
                    Vehicle v = near[i];
                    if (v == null || !v.Exists())
                    {
                        continue;
                    }

                    VehDesc d = Describe(v);
                    TagRecord rec;
                    if (!_tags.TryGetValue(d.Key, out rec))
                    {
                        continue;
                    }

                    seen.Add(d.Key);
                    bool has = Function.Call<bool>(Hash.DECOR_EXIST_ON, v, Decor);
                    int val = has ? Function.Call<int>(Hash.DECOR_GET_INT, v, Decor) : 0;
                    string state = has && val == rec.Token ? "TAG_OK" : (has ? "TAG_VALUE_MISMATCH" : "SAME_PLATE_MODEL_WITHOUT_TAG");
                    if (!rec.Present || v.Handle != rec.LastHandle || state != rec.LastState)
                    {
                        ProbeEnv.Log("IDENTITY_" + state, string.Format(CultureInfo.InvariantCulture,
                            "prevHandle={0} handle={1} decorVal={2} expected={3} {4}", rec.LastHandle, v.Handle, val, rec.Token, d.Text));
                    }

                    rec.Present = true;
                    rec.LastHandle = v.Handle;
                    rec.LastState = state;
                }

                foreach (KeyValuePair<string, TagRecord> kv in _tags)
                {
                    if (kv.Value.Present && !seen.Contains(kv.Key))
                    {
                        kv.Value.Present = false;
                        bool exists = Function.Call<bool>(Hash.DOES_ENTITY_EXIST, kv.Value.LastHandle);
                        ProbeEnv.Log("IDENTITY_OUT_OF_SCAN", string.Format(CultureInfo.InvariantCulture,
                            "key={0} lastHandle={1} handleStillExists={2}", kv.Key, kv.Value.LastHandle, Nat.B(exists)));
                    }
                }
            }
            catch (Exception ex)
            {
                ProbeEnv.Log("PROBE_ERROR", "IdentityProbe tick: " + ex.GetType().Name + ": " + ex.Message);
            }
        }

        /// <summary>Registers the probe decorator, unlocking via SHVDN 3.7 DecoratorInterface.IsLocked if present.</summary>
        private static bool EnsureRegistered()
        {
            if (Function.Call<bool>(Hash.DECOR_IS_REGISTERED_AS_TYPE, Decor, DecorTypeInt))
            {
                return true;
            }

            // DecoratorInterface exists only in SHVDN 3.7 nightlies (feasibility.md E3-1); use reflection so this
            // probe compiles against 3.6.0 and still exercises the 3.7 unlock path when available.
            Type di = typeof(Script).Assembly.GetType("GTA.DecoratorInterface", false);
            PropertyInfo locked = di != null ? di.GetProperty("IsLocked", BindingFlags.Public | BindingFlags.Static) : null;
            ProbeEnv.Log("IDENTITY_DECOR_UNLOCK_API", locked != null ? "present" : "absent");
            try
            {
                if (locked != null)
                {
                    locked.SetValue(null, false);
                }

                Function.Call(Hash.DECOR_REGISTER, Decor, DecorTypeInt);
            }
            finally
            {
                if (locked != null)
                {
                    locked.SetValue(null, true);
                }
            }

            bool ok = Function.Call<bool>(Hash.DECOR_IS_REGISTERED_AS_TYPE, Decor, DecorTypeInt);
            ProbeEnv.Log("IDENTITY_DECOR_REGISTER", "ok=" + Nat.B(ok));
            return ok;
        }

        private static VehDesc Describe(Vehicle v)
        {
            string plate = Function.Call<string>(Hash.GET_VEHICLE_NUMBER_PLATE_TEXT, v);
            int plateIdx = Function.Call<int>(Hash.GET_VEHICLE_NUMBER_PLATE_TEXT_INDEX, v);
            var c1 = new OutputArgument();
            var c2 = new OutputArgument();
            Function.Call(Hash.GET_VEHICLE_COLOURS, v, c1, c2);
            var pearl = new OutputArgument();
            var wheel = new OutputArgument();
            Function.Call(Hash.GET_VEHICLE_EXTRA_COLOURS, v, pearl, wheel);
            int model = v.Model.Hash;
            bool mission = Function.Call<bool>(Hash.IS_ENTITY_A_MISSION_ENTITY, v);
            int pop = Function.Call<int>(Hash.GET_ENTITY_POPULATION_TYPE, v);
            string text = string.Format(CultureInfo.InvariantCulture,
                "handle={0} model=0x{1:X8} plate='{2}' plateIdx={3} col={4}/{5} pearl={6} wheelCol={7} livery={8} tint={9} wheelType={10} modKit={11} mission={12} pop={13} body={14:F0} engine={15:F0} tank={16:F0} dirt={17:F1}",
                v.Handle, model, plate, plateIdx, c1.GetResult<int>(), c2.GetResult<int>(), pearl.GetResult<int>(), wheel.GetResult<int>(),
                Function.Call<int>(Hash.GET_VEHICLE_LIVERY, v), Function.Call<int>(Hash.GET_VEHICLE_WINDOW_TINT, v),
                Function.Call<int>(Hash.GET_VEHICLE_WHEEL_TYPE, v), Function.Call<int>(Hash.GET_VEHICLE_MOD_KIT, v),
                Nat.B(mission), pop, Function.Call<float>(Hash.GET_VEHICLE_BODY_HEALTH, v),
                Function.Call<float>(Hash.GET_VEHICLE_ENGINE_HEALTH, v), Function.Call<float>(Hash.GET_VEHICLE_PETROL_TANK_HEALTH, v),
                Function.Call<float>(Hash.GET_VEHICLE_DIRT_LEVEL, v));
            return new VehDesc { Key = (plate ?? string.Empty).Trim() + "|" + model.ToString("X8", CultureInfo.InvariantCulture), Text = text };
        }

        private struct VehDesc
        {
            public string Key;
            public string Text;
        }

        private sealed class TagRecord
        {
            public int Token;
            public int LastHandle;
            public bool Present;
            public string LastState = string.Empty;
        }
    }
}
