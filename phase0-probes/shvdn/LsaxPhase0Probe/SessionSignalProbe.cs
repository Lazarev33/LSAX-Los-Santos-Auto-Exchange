// =====================================================================================
// DISPOSABLE PHASE 0 FEASIBILITY PROBE — NOT LSAX PRODUCTION CODE. DO NOT SHIP OR REUSE.
// P-SL-01 (DRAFT2): observation of save/load/session signals for LSAX-SAVELOAD-FEASIBILITY.md §6 (PC-1 … PC-8).
// Game-state writes: NONE, except one runtime int decorator "lsax_p0_sess" on the player ped (PC-5/PC-7 session
// token; disable with SessionToken.Enabled=false). No stat, cash, vehicle or save write. Evidence is only logged;
// every PASS/FAIL decision is taken offline from the log (README-PROBES.md).
// Assumptions exercised: A-SL-1, A-SL-3, A-SL-4, A-SL-5, A-SL-6, A-SL-7, A-SL-8, A-SL-9, A-SL-10, A-SL-12, A-SL-13,
// A-SL-14, A-ENV-1.
// =====================================================================================
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using GTA;
using GTA.Math;
using GTA.Native;

namespace LsaxPhase0Probe
{
    public sealed class SessionSignalProbe : Script
    {
        // Candidate names are HYPOTHESES to be tested (STAT_GET_INT returns false for unknown stats).
        private const string DefaultPlaytimeCandidates =
            "TOTAL_PLAYING_TIME,SP0_TOTAL_PLAYING_TIME,SP1_TOTAL_PLAYING_TIME,SP2_TOTAL_PLAYING_TIME,LEADERBOARD_PLAYING_TIME";
        private const string SessionDecor = "lsax_p0_sess";
        private const int MaxFiles = 64;
        private const int FastScanWindowMs = 10000;
        private static readonly string[] CashStats = { "SP0_TOTAL_CASH", "SP1_TOTAL_CASH", "SP2_TOTAL_CASH" };

        private readonly string[] _ptStats;
        private readonly string _saveRoot;
        private readonly bool _tokenEnabled;
        private readonly Dictionary<string, FileSnapshot> _saveFiles = new Dictionary<string, FileSnapshot>(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, BracketRow> _ledger = new Dictionary<string, BracketRow>(StringComparer.OrdinalIgnoreCase);
        private string _lastFlags = string.Empty;
        private Sample _prevTick;               // values read in the previous tick (bracket lower end candidate)
        private Sample _preSignal;              // values at the last tick BEFORE the first save-flag transition
        private DateTime _lastFlagChangeUtc = DateTime.MinValue;
        private DateTime _nextSaveScanUtc;
        private int _token;
        private int _taggedPed;

        public SessionSignalProbe()
        {
            Interval = 0; // every tick: brackets, wallet transitions and tick markers need per-tick samples
            _ptStats = ProbeEnv.Cfg("PlaytimeStatCandidates", DefaultPlaytimeCandidates)
                .Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries).Select(s => s.Trim()).Take(16).ToArray();
            _saveRoot = ProbeEnv.Cfg("SaveRoot",
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "Rockstar Games", "GTA V", "Profiles"));
            _tokenEnabled = !string.Equals(ProbeEnv.Cfg("SessionToken.Enabled", "true"), "false", StringComparison.OrdinalIgnoreCase);

            int domainN = ProbeEnv.IncrementDomainCounter();
            ProbeEnv.Log("CTOR", string.Format(CultureInfo.InvariantCulture,
                "domainInstanceInProcess={0} process={1} appDomain={2} shvdnAsm={3} shvdnFileVersion={4} gameVersion={5} saveRoot={6}",
                domainN, ProbeEnv.ProcessKey(), AppDomain.CurrentDomain.FriendlyName, typeof(Script).Assembly.GetName().Version,
                SafeFileVersion(typeof(Script).Assembly), (int)Game.Version, _saveRoot));

            SafeRun("CTOR_SAMPLE", () =>
            {
                Sample s = Sample.Read(_ptStats);
                _prevTick = s;
                ProbeEnv.Log("CTOR_FP", s + " clock=[" + Nat.Clock() + "] model=0x" + Game.Player.Character.Model.Hash.ToString("X8", CultureInfo.InvariantCulture));
                _lastFlags = Nat.Flags();              // baseline: the first tick must not look like a save signal
                ProbeEnv.Log("CTOR_FLAGS", _lastFlags);
                ProbeEnv.Log("CTOR_SAVEHOUSE_AFTER_LOAD", SaveHouseAfterLoad());
            });
            SafeRun("CTOR_TOKEN", CheckAndTagToken);
            SafeRun("CTOR_LEDGER", LoadLedger);
            SafeRun("CTOR_SAVESCAN", () => ScanSaveFiles(true, null));
            SafeRun("CTOR_LOAD_MATCH", LogLoadMatch);

            Tick += OnTick;
            Aborted += OnAborted;
        }

        private void OnTick(object sender, EventArgs e)
        {
            SafeRun("TICK", () =>
            {
                DateTime now = DateTime.UtcNow;
                Sample s = Sample.Read(_ptStats);

                string flags = Nat.Flags();
                if (flags != _lastFlags)
                {
                    if ((now - _lastFlagChangeUtc).TotalMilliseconds > FastScanWindowMs && _prevTick != null)
                    {
                        _preSignal = _prevTick; // snapshot must lie after this sample (A-SL-12 as used by D-SL-17)
                    }

                    _lastFlagChangeUtc = now;
                    ProbeEnv.Log("FLAGS", flags + " frame=" + s.Frame.ToString(CultureInfo.InvariantCulture) +
                        " preSignal=[" + (_preSignal != null ? _preSignal.ToString() : "-") + "]");
                    _lastFlags = flags;
                }

                LogTransitions(s);
                LogPedChange();

                bool fast = (now - _lastFlagChangeUtc).TotalMilliseconds <= FastScanWindowMs;
                if (fast || now >= _nextSaveScanUtc)
                {
                    _nextSaveScanUtc = now.AddSeconds(2);
                    Dictionary<string, FileSnapshot> before = fast ? MetaOnly() : null;
                    ScanSaveFiles(false, s);
                    if (before != null)
                    {
                        // PC-4 tick markers: a save-file change inside one probe tick would be an interleave witness.
                        Dictionary<string, FileSnapshot> after = MetaOnly();
                        foreach (KeyValuePair<string, FileSnapshot> kv in after)
                        {
                            FileSnapshot b;
                            if (before.TryGetValue(kv.Key, out b) && (b.LastWriteUtc != kv.Value.LastWriteUtc || b.Length != kv.Value.Length))
                            {
                                ProbeEnv.Log("TICK_INTERLEAVE", "file=" + Path.GetFileName(kv.Key) + " frame=" + s.Frame.ToString(CultureInfo.InvariantCulture));
                            }
                        }
                    }
                }

                _prevTick = s;
            });
        }

        // ------------------------------------------------------------------ per-tick evidence
        private void LogTransitions(Sample s)
        {
            if (_prevTick == null)
            {
                return;
            }

            for (int i = 0; i < 3; i++)
            {
                if (s.Cash[i] != _prevTick.Cash[i])
                {
                    ProbeEnv.Log("WALLET_CHANGE", string.Format(CultureInfo.InvariantCulture, "{0}: {1} -> {2} frame={3}",
                        CashStats[i], _prevTick.Cash[i], s.Cash[i], s.Frame));
                }
            }

            foreach (KeyValuePair<string, int> kv in s.Pt)
            {
                int prev;
                if (_prevTick.Pt.TryGetValue(kv.Key, out prev) && kv.Value < prev)
                {
                    ProbeEnv.Log("PT_DECREASED", string.Format(CultureInfo.InvariantCulture, "{0}: {1} -> {2} frame={3} flags=[{4}]",
                        kv.Key, prev, kv.Value, s.Frame, _lastFlags));
                }
            }
        }

        private void LogPedChange()
        {
            Ped ped = Game.Player.Character;
            int h = ped != null ? ped.Handle : 0;
            if (h == _taggedPed || !_tokenEnabled || _token == 0)
            {
                return;
            }

            bool has = h != 0 && Function.Call<bool>(Hash.DECOR_EXIST_ON, ped, SessionDecor);
            int val = has ? Function.Call<int>(Hash.DECOR_GET_INT, ped, SessionDecor) : 0;
            bool retag = h != 0 && Function.Call<bool>(Hash.DECOR_SET_INT, ped, SessionDecor, _token);
            ProbeEnv.Log("TOKEN_PED_CHANGED", string.Format(CultureInfo.InvariantCulture,
                "oldPed={0} newPed={1} newPedHadToken={2} value={3} expected={4} retagOk={5} model=0x{6:X8}",
                _taggedPed, h, Nat.B(has), val, _token, Nat.B(retag), ped != null ? ped.Model.Hash : 0));
            _taggedPed = h;
        }

        // ------------------------------------------------------------------ session token (PC-5, PC-7)
        private void CheckAndTagToken()
        {
            if (!_tokenEnabled)
            {
                ProbeEnv.Log("TOKEN_DISABLED", "SessionToken.Enabled=false");
                return;
            }

            bool registered = ProbeDecor.EnsureRegistered(SessionDecor, "TOKEN");
            string path = Path.Combine(ProbeEnv.Dir, "session-token.txt");
            string expected = File.Exists(path) ? File.ReadAllText(path).Trim() : "<none>";
            Ped ped = Game.Player.Character;
            bool has = registered && Function.Call<bool>(Hash.DECOR_EXIST_ON, ped, SessionDecor);
            int val = has ? Function.Call<int>(Hash.DECOR_GET_INT, ped, SessionDecor) : 0;
            ProbeEnv.Log("TOKEN_AT_CTOR", string.Format(CultureInfo.InvariantCulture,
                "registered={0} present={1} value={2} persisted=[{3}] process={4}",
                Nat.B(registered), Nat.B(has), val, expected, ProbeEnv.ProcessKey()));

            if (!registered)
            {
                return;
            }

            _token = (int)((uint)Guid.NewGuid().GetHashCode() & 0x7FFFFFFF) | 1;
            bool setOk = Function.Call<bool>(Hash.DECOR_SET_INT, ped, SessionDecor, _token);
            bool readBack = Function.Call<int>(Hash.DECOR_GET_INT, ped, SessionDecor) == _token;
            _taggedPed = ped.Handle;
            File.WriteAllText(path, _token.ToString(CultureInfo.InvariantCulture) + " " + ProbeEnv.ProcessKey());
            ProbeEnv.Log("TOKEN_SET", string.Format(CultureInfo.InvariantCulture, "token={0} setOk={1} readBack={2} ped={3}",
                _token, Nat.B(setOk), Nat.B(readBack), ped.Handle));
        }

        // ------------------------------------------------------------------ save files + probe ledger (PC-4, PC-8)
        private Dictionary<string, FileSnapshot> MetaOnly()
        {
            var d = new Dictionary<string, FileSnapshot>(StringComparer.OrdinalIgnoreCase);
            if (!Directory.Exists(_saveRoot))
            {
                return d;
            }

            foreach (string path in Directory.EnumerateFiles(_saveRoot, "SGTA*", SearchOption.AllDirectories).Take(MaxFiles))
            {
                var fi = new FileInfo(path);
                d[path] = new FileSnapshot { LastWriteUtc = fi.LastWriteTimeUtc, Length = fi.Length };
            }

            return d;
        }

        private void ScanSaveFiles(bool initial, Sample now)
        {
            if (!Directory.Exists(_saveRoot))
            {
                if (initial)
                {
                    ProbeEnv.Log("SAVEROOT_MISSING", _saveRoot);
                }

                return;
            }

            foreach (string path in Directory.EnumerateFiles(_saveRoot, "SGTA*", SearchOption.AllDirectories).Take(MaxFiles))
            {
                var fi = new FileInfo(path);
                FileSnapshot prev;
                bool known = _saveFiles.TryGetValue(path, out prev);
                if (known && prev.LastWriteUtc == fi.LastWriteTimeUtc && prev.Length == fi.Length)
                {
                    continue;
                }

                var snap = new FileSnapshot { LastWriteUtc = fi.LastWriteTimeUtc, Length = fi.Length, Sha256 = Sha256(path) };
                _saveFiles[path] = snap;
                if (initial)
                {
                    BracketRow row;
                    bool inLedger = _ledger.TryGetValue(snap.Sha256, out row);
                    ProbeEnv.Log("SAVEFILE_INITIAL", string.Format(CultureInfo.InvariantCulture,
                        "file={0} len={1} mtimeUtc={2:o} sha256={3} inProbeLedger={4}",
                        Path.GetFileName(path), snap.Length, snap.LastWriteUtc, snap.Sha256, Nat.B(inLedger)));
                    continue;
                }

                // Bracket for this file: lower end = last sample before the first save-flag transition in the fast
                // window (D-SL-17); fallback = previous tick. Upper end = now.
                bool signalSeen = (DateTime.UtcNow - _lastFlagChangeUtc).TotalMilliseconds <= FastScanWindowMs && _preSignal != null;
                Sample lo = signalSeen ? _preSignal : _prevTick;
                var bracket = new BracketRow { File = Path.GetFileName(path), Sha = snap.Sha256, Lo = lo, Hi = now };
                _ledger[snap.Sha256] = bracket;
                AppendLedger(bracket);
                ProbeEnv.Log("SAVEFILE_CHANGED", string.Format(CultureInfo.InvariantCulture,
                    "file={0} len={1} mtimeUtc={2:o} sha256={3} signalSeen={4} msSinceFlagChange={5:F0} bracketLo=[{6}] bracketHi=[{7}] walletsStable={8} flags=[{9}]",
                    bracket.File, snap.Length, snap.LastWriteUtc, snap.Sha256, Nat.B(signalSeen),
                    (DateTime.UtcNow - _lastFlagChangeUtc).TotalMilliseconds, lo != null ? lo.ToString() : "-", now,
                    Nat.B(lo != null && lo.SameCash(now)), _lastFlags));
                if (signalSeen)
                {
                    _preSignal = null;
                }
            }
        }

        private void LogLoadMatch()
        {
            // PC-8: after a load (this CTOR), which present files' probe brackets contain the loaded world?
            Sample s = _prevTick;
            if (s == null)
            {
                return;
            }

            foreach (string ptName in _ptStats)
            {
                int pt;
                if (!s.Pt.TryGetValue(ptName, out pt))
                {
                    continue;
                }

                var matches = new List<string>();
                foreach (KeyValuePair<string, FileSnapshot> kv in _saveFiles)
                {
                    BracketRow row;
                    if (!_ledger.TryGetValue(kv.Value.Sha256 ?? string.Empty, out row) || row.Lo == null || row.Hi == null)
                    {
                        continue;
                    }

                    int lo, hi;
                    if (row.Lo.Pt.TryGetValue(ptName, out lo) && row.Hi.Pt.TryGetValue(ptName, out hi) && lo <= pt && pt <= hi)
                    {
                        bool walletsKnown = row.Lo.SameCash(row.Hi);
                        bool walletsEqual = !walletsKnown || row.Hi.SameCash(s);
                        matches.Add(row.File + (walletsKnown ? (walletsEqual ? ":W=" : ":W!=") : ":W?"));
                    }
                }

                ProbeEnv.Log("LOAD_MATCH", string.Format(CultureInfo.InvariantCulture, "pt={0} value={1} matches={2} [{3}] cash=[{4}]",
                    ptName, pt, matches.Count, string.Join(",", matches), s.CashText()));
            }
        }

        private void LoadLedger()
        {
            string path = Path.Combine(ProbeEnv.Dir, "probe-ledger.tsv");
            if (!File.Exists(path))
            {
                return;
            }

            foreach (string line in File.ReadAllLines(path))
            {
                string[] f = line.Split('\t');
                if (f.Length == 4)
                {
                    _ledger[f[1]] = new BracketRow { File = f[0], Sha = f[1], Lo = Sample.Parse(f[2]), Hi = Sample.Parse(f[3]) };
                }
            }

            ProbeEnv.Log("PROBE_LEDGER", "rows=" + _ledger.Count.ToString(CultureInfo.InvariantCulture));
        }

        private static void AppendLedger(BracketRow r)
        {
            File.AppendAllText(Path.Combine(ProbeEnv.Dir, "probe-ledger.tsv"),
                r.File + "\t" + r.Sha + "\t" + (r.Lo != null ? r.Lo.Serialize() : "-") + "\t" + (r.Hi != null ? r.Hi.Serialize() : "-") + Environment.NewLine);
        }

        private void OnAborted(object sender, EventArgs e)
        {
            // PC-6 (informative, A-SL-3): which session does game state belong to when Aborted runs? Read-only.
            SafeRun("ABORTED", () => ProbeEnv.Log("ABORTED", Sample.Read(_ptStats) + " flags=[" + Nat.Flags() + "]"));
        }

        private static string SaveHouseAfterLoad()
        {
            var pos = new OutputArgument();
            var heading = new OutputArgument();
            var fadeIn = new OutputArgument();
            var p3 = new OutputArgument();
            bool ok = Function.Call<bool>(Hash.GET_SAVE_HOUSE_DETAILS_AFTER_SUCCESSFUL_LOAD, pos, heading, fadeIn, p3);
            if (!ok)
            {
                return "ret=0";
            }

            Vector3 v = pos.GetResult<Vector3>();
            return string.Format(CultureInfo.InvariantCulture, "ret=1 pos=({0:F1},{1:F1},{2:F1}) heading={3:F1} fadeIn={4}",
                v.X, v.Y, v.Z, heading.GetResult<float>(), Nat.B(fadeIn.GetResult<bool>()));
        }

        private static string Sha256(string path)
        {
            try
            {
                using (var sha = SHA256.Create())
                using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                {
                    return BitConverter.ToString(sha.ComputeHash(fs)).Replace("-", string.Empty);
                }
            }
            catch (IOException ex)
            {
                return "<io:" + ex.GetType().Name + ">";
            }
            catch (UnauthorizedAccessException)
            {
                return "<denied>";
            }
        }

        private static string SafeFileVersion(System.Reflection.Assembly asm)
        {
            try
            {
                string loc = asm.Location;
                return string.IsNullOrEmpty(loc) ? "<no-location>" : System.Diagnostics.FileVersionInfo.GetVersionInfo(loc).FileVersion;
            }
            catch (Exception ex)
            {
                return "<err:" + ex.GetType().Name + ">";
            }
        }

        private static void SafeRun(string where, Action a)
        {
            try
            {
                a();
            }
            catch (Exception ex)
            {
                // A probe must never abort itself through an unhandled tick exception (feasibility.md E1-7).
                ProbeEnv.Log("PROBE_ERROR", where + ": " + ex.GetType().Name + ": " + ex.Message);
            }
        }

        private struct FileSnapshot
        {
            public DateTime LastWriteUtc;
            public long Length;
            public string Sha256;
        }

        private sealed class BracketRow
        {
            public string File;
            public string Sha;
            public Sample Lo;
            public Sample Hi;
        }

        /// <summary>One tick's reading: frame, game timer, the three wallets and the play-time candidates.</summary>
        private sealed class Sample
        {
            public int Frame;
            public int GameTime;
            public readonly int[] Cash = new int[3];
            public readonly Dictionary<string, int> Pt = new Dictionary<string, int>(StringComparer.Ordinal);

            public static Sample Read(IEnumerable<string> ptStats)
            {
                var s = new Sample { Frame = Function.Call<int>(Hash.GET_FRAME_COUNT), GameTime = Game.GameTime };
                for (int i = 0; i < 3; i++)
                {
                    int v;
                    s.Cash[i] = Nat.TryStatInt(CashStats[i], out v) ? v : int.MinValue;
                }

                foreach (string name in ptStats)
                {
                    int v;
                    if (Nat.TryStatInt(name, out v))
                    {
                        s.Pt[name] = v;
                    }
                }

                return s;
            }

            public bool SameCash(Sample o)
            {
                return o != null && Cash[0] == o.Cash[0] && Cash[1] == o.Cash[1] && Cash[2] == o.Cash[2];
            }

            public string CashText()
            {
                return string.Join(",", Cash.Select(c => c.ToString(CultureInfo.InvariantCulture)));
            }

            public string Serialize()
            {
                return Frame.ToString(CultureInfo.InvariantCulture) + ";" + GameTime.ToString(CultureInfo.InvariantCulture) + ";" + CashText() + ";" +
                       string.Join(",", Pt.Select(kv => kv.Key + "=" + kv.Value.ToString(CultureInfo.InvariantCulture)));
            }

            public static Sample Parse(string text)
            {
                if (text == "-")
                {
                    return null;
                }

                string[] p = text.Split(';');
                var s = new Sample
                {
                    Frame = int.Parse(p[0], CultureInfo.InvariantCulture),
                    GameTime = int.Parse(p[1], CultureInfo.InvariantCulture),
                };
                string[] c = p[2].Split(',');
                for (int i = 0; i < 3; i++)
                {
                    s.Cash[i] = int.Parse(c[i], CultureInfo.InvariantCulture);
                }

                if (p.Length > 3 && p[3].Length > 0)
                {
                    foreach (string kv in p[3].Split(','))
                    {
                        int eq = kv.IndexOf('=');
                        s.Pt[kv.Substring(0, eq)] = int.Parse(kv.Substring(eq + 1), CultureInfo.InvariantCulture);
                    }
                }

                return s;
            }

            public override string ToString()
            {
                return "frame=" + Frame.ToString(CultureInfo.InvariantCulture) + " gameTime=" + GameTime.ToString(CultureInfo.InvariantCulture) +
                       " cash=" + CashText() + " pt=" + string.Join(",", Pt.Select(kv => kv.Key + "=" + kv.Value.ToString(CultureInfo.InvariantCulture)));
            }
        }
    }
}
