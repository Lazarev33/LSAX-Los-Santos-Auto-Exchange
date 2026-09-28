// =====================================================================================
// DISPOSABLE PHASE 0 FEASIBILITY PROBE — NOT LSAX PRODUCTION CODE. DO NOT SHIP OR REUSE.
// P-SL-02: tests whether an SP integer stat can carry an LSAX watermark through GTA save/load.
// WRITES GAME STATS. Disabled unless probe.ini contains BOTH:
//   AnchorProbe.Enabled=true
//   AnchorProbe.Consent=I_USE_A_DISPOSABLE_SAVE
// Candidate stat names are supplied by the tester (AnchorProbe.CandidateStats); none are assumed safe.
// =====================================================================================
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using GTA;

namespace LsaxPhase0Probe
{
    public sealed class AnchorCarrierProbe : Script
    {
        private const string ConsentPhrase = "I_USE_A_DISPOSABLE_SAVE";
        private readonly bool _enabled;
        private readonly string[] _candidates;
        private readonly Keys _writeKey;
        private readonly Keys _restoreKey;
        private readonly string _journalPath;

        public AnchorCarrierProbe()
        {
            _enabled = ProbeEnv.CfgBool("AnchorProbe.Enabled")
                && ProbeEnv.Cfg("AnchorProbe.Consent", string.Empty) == ConsentPhrase;
            _candidates = ProbeEnv.Cfg("AnchorProbe.CandidateStats", string.Empty)
                .Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(s => s.Trim())
                .Where(s => s.Length > 0)
                .Take(8)
                .ToArray();
            _writeKey = ParseKey(ProbeEnv.Cfg("AnchorProbe.WriteKey", "F9"), Keys.F9);
            _restoreKey = ParseKey(ProbeEnv.Cfg("AnchorProbe.RestoreKey", "F11"), Keys.F11);
            _journalPath = Path.Combine(ProbeEnv.Dir, "anchor-journal.tsv");

            if (!_enabled)
            {
                ProbeEnv.Log("ANCHOR_DISABLED", "set AnchorProbe.Enabled=true and AnchorProbe.Consent=" + ConsentPhrase);
                return;
            }

            // On every construction (process start or domain reload), report what the loaded game carries.
            List<JournalRow> journal = ReadJournal();
            foreach (string stat in _candidates)
            {
                int v;
                bool exists = Nat.TryStatInt(stat, out v);
                JournalRow match = journal.LastOrDefault(r => r.Stat == stat && r.Written == v);
                ProbeEnv.Log("ANCHOR_READBACK", string.Format(CultureInfo.InvariantCulture,
                    "stat={0} exists={1} value={2} matchesJournalSeq={3}",
                    stat, Nat.B(exists), exists ? v.ToString(CultureInfo.InvariantCulture) : "-",
                    match != null ? match.Seq.ToString(CultureInfo.InvariantCulture) : "none"));
            }

            KeyDown += OnKeyDown;
        }

        private void OnKeyDown(object sender, KeyEventArgs e)
        {
            try
            {
                if (e.KeyCode == _writeKey)
                {
                    WriteTokens();
                }
                else if (e.KeyCode == _restoreKey)
                {
                    RestoreOriginals();
                }
            }
            catch (Exception ex)
            {
                ProbeEnv.Log("PROBE_ERROR", "AnchorCarrierProbe: " + ex.GetType().Name + ": " + ex.Message);
            }
        }

        private void WriteTokens()
        {
            List<JournalRow> journal = ReadJournal();
            int seq = journal.Count == 0 ? 1 : journal.Max(r => r.Seq) + 1;
            foreach (string stat in _candidates)
            {
                int original;
                if (!Nat.TryStatInt(stat, out original))
                {
                    ProbeEnv.Log("ANCHOR_SKIP_ABSENT", stat);
                    continue;
                }

                // Distinctive positive token: 0x4C53 ("LS") in the high half, sequence in the low half.
                int token = 0x4C530000 | (seq & 0xFFFF);
                bool setOk = Nat.StatSetInt(stat, token);
                int readBack;
                bool readOk = Nat.TryStatInt(stat, out readBack);
                AppendJournal(new JournalRow { Seq = seq, Stat = stat, Original = original, Written = token });
                ProbeEnv.Log("ANCHOR_WRITE", string.Format(CultureInfo.InvariantCulture,
                    "seq={0} stat={1} original={2} token=0x{3:X8} setOk={4} readBackOk={5} readBack=0x{6:X8} gameTime={7}",
                    seq, stat, original, token, Nat.B(setOk), Nat.B(readOk), readBack, Game.GameTime));
            }

            GTA.UI.Notification.Show("LSAX P0 probe: anchor tokens written, seq " + seq.ToString(CultureInfo.InvariantCulture));
        }

        private void RestoreOriginals()
        {
            foreach (IGrouping<string, JournalRow> g in ReadJournal().GroupBy(r => r.Stat))
            {
                JournalRow first = g.OrderBy(r => r.Seq).First();
                bool ok = Nat.StatSetInt(first.Stat, first.Original);
                ProbeEnv.Log("ANCHOR_RESTORE", first.Stat + " -> " + first.Original.ToString(CultureInfo.InvariantCulture) + " ok=" + Nat.B(ok));
            }

            GTA.UI.Notification.Show("LSAX P0 probe: original stat values restored (save the game to persist).");
        }

        private List<JournalRow> ReadJournal()
        {
            var rows = new List<JournalRow>();
            if (!File.Exists(_journalPath))
            {
                return rows;
            }

            foreach (string line in File.ReadAllLines(_journalPath))
            {
                string[] p = line.Split('\t');
                int seq, orig, wr;
                if (p.Length == 4
                    && int.TryParse(p[0], NumberStyles.Integer, CultureInfo.InvariantCulture, out seq)
                    && int.TryParse(p[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out orig)
                    && int.TryParse(p[3], NumberStyles.Integer, CultureInfo.InvariantCulture, out wr))
                {
                    rows.Add(new JournalRow { Seq = seq, Stat = p[1], Original = orig, Written = wr });
                }
            }

            return rows;
        }

        private void AppendJournal(JournalRow r)
        {
            File.AppendAllText(_journalPath, string.Format(CultureInfo.InvariantCulture, "{0}\t{1}\t{2}\t{3}{4}",
                r.Seq, r.Stat, r.Original, r.Written, Environment.NewLine));
        }

        private static Keys ParseKey(string s, Keys fallback)
        {
            Keys k;
            return Enum.TryParse(s, true, out k) ? k : fallback;
        }

        private sealed class JournalRow
        {
            public int Seq;
            public string Stat;
            public int Original;
            public int Written;
        }
    }
}
