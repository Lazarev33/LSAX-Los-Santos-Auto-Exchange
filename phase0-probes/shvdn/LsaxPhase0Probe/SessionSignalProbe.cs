// =====================================================================================
// DISPOSABLE PHASE 0 FEASIBILITY PROBE — NOT LSAX PRODUCTION CODE. DO NOT SHIP OR REUSE.
// P-SL-01: passive observation of save/load/session signals. Performs NO game-state writes.
// Answers (see LSAX-SAVELOAD-FEASIBILITY.md §5): A-SL-1 (domain reload on SP load), A-SL-3 (Aborted timing),
// A-SL-5 (cash restored on load), A-SL-6 (persisted monotonic play-time stat), A-SL-7 (save file writes
// observable), GET_GAME_TIMER behaviour across load, save-status native semantics.
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

        private readonly string[] _extraStats;
        private readonly Dictionary<string, FileSnapshot> _saveFiles = new Dictionary<string, FileSnapshot>(StringComparer.OrdinalIgnoreCase);
        private readonly string _saveRoot;
        private string _lastFlags = string.Empty;
        private Fingerprint _lastFp;
        private DateTime _lastFpUtc;
        private DateTime _nextStatPollUtc;
        private DateTime _nextSaveScanUtc;

        public SessionSignalProbe()
        {
            Interval = 250;
            _extraStats = ProbeEnv.Cfg("PlaytimeStatCandidates", DefaultPlaytimeCandidates)
                .Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(s => s.Trim())
                .Take(32) // bounded
                .ToArray();
            _saveRoot = ProbeEnv.Cfg("SaveRoot",
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "Rockstar Games", "GTA V", "Profiles"));

            int domainN = ProbeEnv.IncrementDomainCounter();
            string shvdnFile = SafeFileVersion(typeof(Script).Assembly);
            ProbeEnv.Log("CTOR", string.Format(CultureInfo.InvariantCulture,
                "domainInstanceInProcess={0} appDomain={1} shvdnAsm={2} shvdnFileVersion={3} gameVersion={4} saveRoot={5}",
                domainN, AppDomain.CurrentDomain.FriendlyName, typeof(Script).Assembly.GetName().Version,
                shvdnFile, (int)Game.Version, _saveRoot));

            SafeRun("CTOR_FP", () =>
            {
                _lastFp = Fingerprint.Capture(_extraStats);
                _lastFpUtc = DateTime.UtcNow;
                ProbeEnv.Log("CTOR_FP", _lastFp.ToString());
                ProbeEnv.Log("CTOR_FLAGS", Nat.Flags());
                ProbeEnv.Log("CTOR_SAVEHOUSE_AFTER_LOAD", SaveHouseAfterLoad());
            });

            SafeRun("CTOR_SAVESCAN", () => ScanSaveFiles(true));

            Tick += OnTick;
            Aborted += OnAborted;
        }

        private void OnTick(object sender, EventArgs e)
        {
            SafeRun("TICK", () =>
            {
                DateTime now = DateTime.UtcNow;

                string flags = Nat.Flags();
                if (flags != _lastFlags)
                {
                    ProbeEnv.Log("FLAGS", flags + " gameTime=" + Game.GameTime.ToString(CultureInfo.InvariantCulture));
                    _lastFlags = flags;
                }

                if (now >= _nextStatPollUtc)
                {
                    _nextStatPollUtc = now.AddSeconds(1);
                    PollFingerprint(now);
                }

                if (now >= _nextSaveScanUtc)
                {
                    _nextSaveScanUtc = now.AddSeconds(2);
                    ScanSaveFiles(false);
                }
            });
        }

        private void PollFingerprint(DateTime now)
        {
            Fingerprint fp = Fingerprint.Capture(_extraStats);
            if (_lastFp != null)
            {
                double wallMs = (now - _lastFpUtc).TotalMilliseconds;
                if (fp.GameTime < _lastFp.GameTime)
                {
                    ProbeEnv.Log("GAMETIMER_DECREASED", _lastFp.GameTime + " -> " + fp.GameTime);
                }

                foreach (KeyValuePair<string, int> kv in fp.StatValues)
                {
                    int prev;
                    if (!_lastFp.StatValues.TryGetValue(kv.Key, out prev) || prev == kv.Value)
                    {
                        continue;
                    }

                    long delta = (long)kv.Value - prev;
                    // Play-time candidates: log decreases and jumps larger than wall-clock elapsed + 5 s.
                    string kind = delta < 0 ? "STAT_DECREASED" : (delta > wallMs + 5000 ? "STAT_JUMP" : "STAT_CHANGED");
                    if (kind != "STAT_CHANGED" || kv.Key.EndsWith("_CASH", StringComparison.Ordinal))
                    {
                        ProbeEnv.Log(kind, string.Format(CultureInfo.InvariantCulture, "{0}: {1} -> {2} (wallMs={3:F0})", kv.Key, prev, kv.Value, wallMs));
                    }
                }

                if (fp.PlayerModel != _lastFp.PlayerModel)
                {
                    ProbeEnv.Log("PLAYER_MODEL_CHANGED", string.Format(CultureInfo.InvariantCulture, "0x{0:X8} -> 0x{1:X8}", _lastFp.PlayerModel, fp.PlayerModel));
                }
            }

            _lastFp = fp;
            _lastFpUtc = now;
        }

        private void ScanSaveFiles(bool initial)
        {
            if (!Directory.Exists(_saveRoot))
            {
                if (initial)
                {
                    ProbeEnv.Log("SAVEROOT_MISSING", _saveRoot);
                }

                return;
            }

            int seen = 0;
            foreach (string path in Directory.EnumerateFiles(_saveRoot, "SGTA*", SearchOption.AllDirectories))
            {
                if (++seen > 64)
                {
                    break; // bounded scan
                }

                var fi = new FileInfo(path);
                FileSnapshot prev;
                bool known = _saveFiles.TryGetValue(path, out prev);
                if (known && prev.LastWriteUtc == fi.LastWriteTimeUtc && prev.Length == fi.Length)
                {
                    continue;
                }

                var snap = new FileSnapshot { LastWriteUtc = fi.LastWriteTimeUtc, Length = fi.Length, Sha256 = Sha256(path) };
                _saveFiles[path] = snap;
                string fp = _lastFp != null ? _lastFp.ToString() : "<none>";
                ProbeEnv.Log(initial ? "SAVEFILE_INITIAL" : "SAVEFILE_CHANGED", string.Format(CultureInfo.InvariantCulture,
                    "file={0} len={1} mtimeUtc={2:o} sha256={3} fpAtDetection=[{4}]",
                    Path.GetFileName(path), snap.Length, snap.LastWriteUtc, snap.Sha256, initial ? "-" : fp));
            }
        }

        private void OnAborted(object sender, EventArgs e)
        {
            // Evidence for E1-4: which session does game state belong to when Aborted runs?
            SafeRun("ABORTED", () =>
            {
                Fingerprint fp = Fingerprint.Capture(_extraStats);
                ProbeEnv.Log("ABORTED", fp + " flags=[" + Nat.Flags() + "]");
            });
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
    }
}
