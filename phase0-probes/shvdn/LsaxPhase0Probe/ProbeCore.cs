// =====================================================================================
// DISPOSABLE PHASE 0 FEASIBILITY PROBE — NOT LSAX PRODUCTION CODE. DO NOT SHIP OR REUSE.
// Purpose: collect runtime evidence for LSAX-SAVELOAD-FEASIBILITY.md (P-SL-01, P-SL-02, P-ID-01).
// Every native used here was checked against alloc8or/gta5-nativedb-data@424fb51 and the
// ScriptHookVDotNet3 3.6.0 reference assembly (compile check). Runtime behaviour is UNKNOWN until run.
// =====================================================================================
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using GTA;
using GTA.Native;

namespace LsaxPhase0Probe
{
    /// <summary>Probe folder, config and a bounded append-only log.</summary>
    internal static class ProbeEnv
    {
        private const int MaxLinesPerDomain = 20000;
        private static readonly object Sync = new object();
        private static string _dir;
        private static string _logPath;
        private static int _lines;
        private static Dictionary<string, string> _cfg;

        public static string Dir
        {
            get { Init(); return _dir; }
        }

        public static void Init()
        {
            lock (Sync)
            {
                if (_dir != null)
                {
                    return;
                }

                // SHVDN sets the script AppDomain ApplicationBase to the scripts directory (ScriptDomain.cs, AppDomainSetup).
                _dir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "LSAXProbe");
                Directory.CreateDirectory(_dir);
                _logPath = Path.Combine(_dir, "probe-" + DateTime.UtcNow.ToString("yyyyMMdd", CultureInfo.InvariantCulture) + ".log");
                _cfg = ReadIni(Path.Combine(_dir, "probe.ini"));
            }
        }

        public static string Cfg(string key, string fallback)
        {
            Init();
            string v;
            return _cfg.TryGetValue(key, out v) ? v : fallback;
        }

        public static bool CfgBool(string key)
        {
            return string.Equals(Cfg(key, "false"), "true", StringComparison.OrdinalIgnoreCase);
        }

        public static void Log(string evt, string data)
        {
            Init();
            lock (Sync)
            {
                if (_lines >= MaxLinesPerDomain)
                {
                    return;
                }

                _lines++;
                string line = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture) + "\t" + evt + "\t" + data + Environment.NewLine;
                try
                {
                    File.AppendAllText(_logPath, line, Encoding.UTF8);
                }
                catch (IOException)
                {
                    // Probe logging is best effort.
                }
            }
        }

        /// <summary>Counts how many times a probe domain was constructed inside this OS process.</summary>
        public static int IncrementDomainCounter()
        {
            string path = Path.Combine(Dir, "domains-" + ProcessKey() + ".count");
            int n = 0;
            if (File.Exists(path))
            {
                int.TryParse(File.ReadAllText(path).Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out n);
            }

            n++;
            File.WriteAllText(path, n.ToString(CultureInfo.InvariantCulture));
            return n;
        }

        /// <summary>Process identity (S16): OS process id + start time; distinguishes a game restart from a reload.</summary>
        public static string ProcessKey()
        {
            Process p = Process.GetCurrentProcess();
            return p.Id.ToString(CultureInfo.InvariantCulture) + "-" + p.StartTime.ToUniversalTime().Ticks.ToString(CultureInfo.InvariantCulture);
        }

        private static Dictionary<string, string> ReadIni(string path)
        {
            var d = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            if (!File.Exists(path))
            {
                return d;
            }

            foreach (string raw in File.ReadAllLines(path))
            {
                string line = raw.Trim();
                if (line.Length == 0 || line[0] == ';' || line[0] == '#')
                {
                    continue;
                }

                int eq = line.IndexOf('=');
                if (eq > 0)
                {
                    d[line.Substring(0, eq).Trim()] = line.Substring(eq + 1).Trim();
                }
            }

            return d;
        }
    }

    /// <summary>Thin wrappers over natives that exist in the native DB (see feasibility.md E4).</summary>
    internal static class Nat
    {
        public static bool TryStatInt(string statName, out int value)
        {
            var o = new OutputArgument();
            bool ok = Function.Call<bool>(Hash.STAT_GET_INT, Game.GenerateHash(statName), o, -1);
            value = ok ? o.GetResult<int>() : 0;
            return ok;
        }

        public static bool StatSetInt(string statName, int value)
        {
            return Function.Call<bool>(Hash.STAT_SET_INT, Game.GenerateHash(statName), value, true);
        }

        public static string Clock()
        {
            return string.Format(CultureInfo.InvariantCulture, "{0:D4}-{1:D2}-{2:D2} {3:D2}:{4:D2}:{5:D2} dow={6} msPerMin={7}",
                Function.Call<int>(Hash.GET_CLOCK_YEAR),
                Function.Call<int>(Hash.GET_CLOCK_MONTH) + 1, // native month is 0-based per SHVDN GameClock.Month0
                Function.Call<int>(Hash.GET_CLOCK_DAY_OF_MONTH),
                Function.Call<int>(Hash.GET_CLOCK_HOURS),
                Function.Call<int>(Hash.GET_CLOCK_MINUTES),
                Function.Call<int>(Hash.GET_CLOCK_SECONDS),
                Function.Call<int>(Hash.GET_CLOCK_DAY_OF_WEEK),
                Function.Call<int>(Hash.GET_MILLISECONDS_PER_GAME_MINUTE));
        }

        public static string Flags()
        {
            return string.Format(CultureInfo.InvariantCulture,
                "autosave={0} manualSaveStatus={1} codeReqAutosave={2} pause={3} fadedOut={4} switch={5} loadingScreen={6} missionFlag={7}",
                B(Function.Call<bool>(Hash.IS_AUTO_SAVE_IN_PROGRESS)),
                Function.Call<int>(Hash.GET_STATUS_OF_MANUAL_SAVE),
                B(Function.Call<bool>(Hash.HAS_CODE_REQUESTED_AUTOSAVE)),
                B(Function.Call<bool>(Hash.IS_PAUSE_MENU_ACTIVE)),
                B(Function.Call<bool>(Hash.IS_SCREEN_FADED_OUT)),
                B(Function.Call<bool>(Hash.IS_PLAYER_SWITCH_IN_PROGRESS)),
                B(Function.Call<bool>(Hash.GET_IS_LOADING_SCREEN_ACTIVE)),
                B(Function.Call<bool>(Hash.GET_MISSION_FLAG)));
        }

        public static string B(bool b)
        {
            return b ? "1" : "0";
        }
    }

    /// <summary>Decorator registration shared by P-SL-01 (session token) and P-ID-01 (vehicle tag).</summary>
    internal static class ProbeDecor
    {
        public const int TypeInt = 3; // eDecorType.DECOR_TYPE_INT (native DB comment on DECOR_REGISTER)

        /// <summary>Registers an int decorator, unlocking via SHVDN 3.7 DecoratorInterface.IsLocked if present.</summary>
        public static bool EnsureRegistered(string name, string logPrefix)
        {
            if (Function.Call<bool>(Hash.DECOR_IS_REGISTERED_AS_TYPE, name, TypeInt))
            {
                return true;
            }

            // DecoratorInterface exists only in SHVDN 3.7 nightlies (feasibility.md E3-1); reflection keeps this
            // probe compiling against 3.6.0 while still exercising the 3.7 unlock path when available.
            Type di = typeof(Script).Assembly.GetType("GTA.DecoratorInterface", false);
            PropertyInfo locked = di != null ? di.GetProperty("IsLocked", BindingFlags.Public | BindingFlags.Static) : null;
            ProbeEnv.Log(logPrefix + "_DECOR_UNLOCK_API", locked != null ? "present" : "absent");
            try
            {
                if (locked != null)
                {
                    locked.SetValue(null, false);
                }

                Function.Call(Hash.DECOR_REGISTER, name, TypeInt);
            }
            finally
            {
                if (locked != null)
                {
                    locked.SetValue(null, true);
                }
            }

            bool ok = Function.Call<bool>(Hash.DECOR_IS_REGISTERED_AS_TYPE, name, TypeInt);
            ProbeEnv.Log(logPrefix + "_DECOR_REGISTER", "name=" + name + " ok=" + Nat.B(ok));
            return ok;
        }
    }

    /// <summary>A comparable snapshot of save-embedded candidates. Built once per poll; small and bounded.</summary>
    internal sealed class Fingerprint
    {
        private static readonly string[] CashStats = { "SP0_TOTAL_CASH", "SP1_TOTAL_CASH", "SP2_TOTAL_CASH" };

        public int GameTime;
        public int FrameCount;
        public string Clock;
        public int PlayerModel;
        public int PlayerMoney;
        public readonly List<string> Stats = new List<string>();
        public readonly Dictionary<string, int> StatValues = new Dictionary<string, int>(StringComparer.Ordinal);

        public static Fingerprint Capture(IEnumerable<string> extraStatNames)
        {
            var f = new Fingerprint
            {
                GameTime = Game.GameTime,
                FrameCount = Function.Call<int>(Hash.GET_FRAME_COUNT),
                Clock = Nat.Clock(),
                PlayerModel = Game.Player.Character.Model.Hash,
                PlayerMoney = Game.Player.Money,
            };

            foreach (string s in CashStats)
            {
                f.AddStat(s);
            }

            foreach (string s in extraStatNames)
            {
                f.AddStat(s);
            }

            return f;
        }

        private void AddStat(string name)
        {
            int v;
            bool ok = Nat.TryStatInt(name, out v);
            Stats.Add(name + "=" + (ok ? v.ToString(CultureInfo.InvariantCulture) : "<absent>"));
            if (ok)
            {
                StatValues[name] = v;
            }
        }

        public override string ToString()
        {
            return string.Format(CultureInfo.InvariantCulture, "gameTime={0} frame={1} clock=[{2}] model=0x{3:X8} money={4} stats=[{5}]",
                GameTime, FrameCount, Clock, PlayerModel, PlayerMoney, string.Join(" ", Stats));
        }
    }
}
