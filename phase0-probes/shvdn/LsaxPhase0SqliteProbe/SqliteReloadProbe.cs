// =====================================================================================
// DISPOSABLE PHASE 0 FEASIBILITY PROBE — NOT LSAX PRODUCTION CODE. DO NOT SHIP OR REUSE.
// P-DB-01 (DRAFT2): can Microsoft.Data.Sqlite + native e_sqlite3 load inside SHVDN's shadow-copied script AppDomain,
// survive repeated domain reloads (console `Reload`, SP save load), commit durably within tick budget, and run the
// D-DB-4 architecture (journal file + ATTACHed projection file, journal-then-projection commits, online backup of
// schema `proj` only, journal backup, snapshot restore into the attached schema)? Writes only its own files under
// scripts/LSAXProbe/ (p0.db, p0_proj.db, p0_snap.db, p0_journal_backup.db). Never touches game state.
// Opt-in: scripts/LSAXProbe/probe.ini  SqliteProbe.Enabled=true
// Optional: SqliteProbe.NativePath=<absolute path to e_sqlite3.dll> (pre-loaded with LoadLibraryW)
//           SqliteProbe.CloseOnAbort=false  (leak test: do NOT close the connection in Aborted)
// =====================================================================================
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using GTA;
using Microsoft.Data.Sqlite;

namespace LsaxPhase0SqliteProbe
{
    public sealed class SqliteReloadProbe : Script
    {
        private readonly string _dir;
        private readonly Dictionary<string, string> _cfg;
        private SqliteConnection _conn;

        public SqliteReloadProbe()
        {
            _dir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "LSAXProbe");
            Directory.CreateDirectory(_dir);
            _cfg = ReadIni(Path.Combine(_dir, "probe.ini"));
            if (!Flag("SqliteProbe.Enabled", false))
            {
                return;
            }

            Log("SQL_CTOR", string.Format(CultureInfo.InvariantCulture, "baseDir={0} asmLocation={1} codeBase={2}",
                AppDomain.CurrentDomain.BaseDirectory, typeof(SqliteReloadProbe).Assembly.Location, typeof(SqliteReloadProbe).Assembly.CodeBase));

            string native;
            if (_cfg.TryGetValue("SqliteProbe.NativePath", out native) && native.Length > 0)
            {
                IntPtr h = LoadLibraryW(native);
                Log("SQL_PRELOAD", "path=" + native + " ok=" + (h != IntPtr.Zero) + " win32err=" + Marshal.GetLastWin32Error());
            }

            try
            {
                var sw = Stopwatch.StartNew();
                _conn = new SqliteConnection("Data Source=" + Path.Combine(_dir, "p0.db") + ";Pooling=False");
                _conn.Open();
                Exec("PRAGMA journal_mode=WAL;");
                Exec("PRAGMA synchronous=FULL;");
                Exec("PRAGMA busy_timeout=2000;");
                Exec("CREATE TABLE IF NOT EXISTS probe_row(id INTEGER PRIMARY KEY, utc TEXT NOT NULL, pid INTEGER NOT NULL);");
                Log("SQL_OPEN", string.Format(CultureInfo.InvariantCulture, "ms={0} sqlite={1} journal={2} nativeModule={3}",
                    sw.ElapsedMilliseconds, Scalar("SELECT sqlite_version();"), Scalar("PRAGMA journal_mode;"), NativeModulePath()));

                var times = new List<long>();
                for (int i = 0; i < 20; i++)
                {
                    sw.Restart();
                    using (SqliteTransaction tx = _conn.BeginTransaction())
                    using (SqliteCommand c = _conn.CreateCommand())
                    {
                        c.Transaction = tx;
                        c.CommandText = "INSERT INTO probe_row(utc, pid) VALUES ($u, $p);";
                        c.Parameters.AddWithValue("$u", DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture));
                        c.Parameters.AddWithValue("$p", Process.GetCurrentProcess().Id);
                        c.ExecuteNonQuery();
                        tx.Commit();
                    }

                    times.Add(sw.ElapsedTicks * 1000000L / Stopwatch.Frequency);
                }

                times.Sort();
                Log("SQL_COMMIT_US", string.Format(CultureInfo.InvariantCulture, "n=20 p50={0} p95={1} max={2} rows={3}",
                    times[10], times[18], times[19], Scalar("SELECT COUNT(*) FROM probe_row;")));
                LogDependencies();
                TwoFileArchitecture();
            }
            catch (Exception ex)
            {
                Log("SQL_FAIL", ex.GetType().FullName + ": " + ex.Message + " inner=" + (ex.InnerException != null ? ex.InnerException.Message : "-"));
            }

            Aborted += OnAborted;
        }

        /// <summary>R-COMP-2: where every SQLite-related assembly was resolved from (first EndsWith match wins in SHVDN).</summary>
        private void LogDependencies()
        {
            foreach (System.Reflection.Assembly a in AppDomain.CurrentDomain.GetAssemblies())
            {
                string n = a.GetName().Name;
                if (n.IndexOf("Sqlite", StringComparison.OrdinalIgnoreCase) >= 0 || n.StartsWith("SQLitePCL", StringComparison.Ordinal) ||
                    n.StartsWith("System.Memory", StringComparison.Ordinal) || n.StartsWith("System.Buffers", StringComparison.Ordinal))
                {
                    string loc;
                    try
                    {
                        loc = a.IsDynamic ? "<dynamic>" : a.Location;
                    }
                    catch (NotSupportedException)
                    {
                        loc = "<n/a>";
                    }

                    Log("SQL_DEPENDENCY", n + " version=" + a.GetName().Version + " location=" + loc);
                }
            }
        }

        /// <summary>D-DB-4 exercised exactly as specified (LSAX-DB-SCHEMA-DRAFT.md §1, §5).</summary>
        private void TwoFileArchitecture()
        {
            string proj = Path.Combine(_dir, "p0_proj.db");
            Exec("ATTACH DATABASE '" + proj.Replace("'", "''") + "' AS proj;");
            Exec("PRAGMA proj.journal_mode=WAL;");
            Exec("PRAGMA proj.synchronous=NORMAL;");
            Exec("CREATE TABLE IF NOT EXISTS proj.projection_meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);");
            Exec("CREATE TABLE IF NOT EXISTS proj.vehicle(id INTEGER PRIMARY KEY, utc TEXT NOT NULL);");
            Log("SQL_PRAGMAS", string.Format(CultureInfo.InvariantCulture, "main.synchronous={0} proj.synchronous={1} proj.journal={2}",
                Scalar("PRAGMA main.synchronous;"), Scalar("PRAGMA proj.synchronous;"), Scalar("PRAGMA proj.journal_mode;")));

            // Lag check first: an unclean stop between the two commits leaves the watermark behind the journal.
            Log("SQL_WATERMARK_AT_START", string.Format(CultureInfo.InvariantCulture, "journalMax={0} watermark={1}",
                Scalar("SELECT COALESCE(MAX(id),0) FROM main.probe_row;"),
                Scalar("SELECT COALESCE((SELECT v FROM proj.projection_meta WHERE k='watermark'),'<none>');")));

            var jt = new List<long>();
            var pt = new List<long>();
            var sw = new Stopwatch();
            for (int i = 0; i < 20; i++)
            {
                sw.Restart();
                long id;
                using (SqliteTransaction tx = _conn.BeginTransaction())
                using (SqliteCommand c = _conn.CreateCommand())
                {
                    c.Transaction = tx;
                    c.CommandText = "INSERT INTO main.probe_row(utc, pid) VALUES ($u, $p); SELECT last_insert_rowid();";
                    c.Parameters.AddWithValue("$u", DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture));
                    c.Parameters.AddWithValue("$p", Process.GetCurrentProcess().Id);
                    id = (long)c.ExecuteScalar();
                    tx.Commit();
                }

                jt.Add(sw.ElapsedTicks * 1000000L / Stopwatch.Frequency);
                sw.Restart();
                using (SqliteTransaction tx = _conn.BeginTransaction())
                using (SqliteCommand c = _conn.CreateCommand())
                {
                    c.Transaction = tx;
                    c.CommandText = "INSERT OR REPLACE INTO proj.vehicle(id, utc) VALUES ($i, $u); " +
                                    "INSERT OR REPLACE INTO proj.projection_meta(k, v) VALUES ('watermark', $w);";
                    c.Parameters.AddWithValue("$i", id);
                    c.Parameters.AddWithValue("$u", DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture));
                    c.Parameters.AddWithValue("$w", id.ToString(CultureInfo.InvariantCulture));
                    c.ExecuteNonQuery();
                    tx.Commit();
                }

                pt.Add(sw.ElapsedTicks * 1000000L / Stopwatch.Frequency);
            }

            jt.Sort();
            pt.Sort();
            Log("SQL_TWO_FILE_COMMIT_US", string.Format(CultureInfo.InvariantCulture,
                "n=20 journal(FULL) p50={0} p95={1} max={2} projection(NORMAL) p50={3} p95={4} max={5}",
                jt[10], jt[18], jt[19], pt[10], pt[18], pt[19]));

            string snap = Path.Combine(_dir, "p0_snap.db");
            string jb = Path.Combine(_dir, "p0_journal_backup.db");
            File.Delete(snap);
            File.Delete(jb);
            using (var dst = new SqliteConnection("Data Source=" + snap + ";Pooling=False"))
            {
                dst.Open();
                _conn.BackupDatabase(dst, "main", "proj");   // projection snapshot = schema proj only
                Log("SQL_SNAPSHOT", "tables=[" + Tables(dst) + "] watermark=" + ScalarOn(dst, "SELECT v FROM projection_meta WHERE k='watermark';"));
            }

            using (var dst = new SqliteConnection("Data Source=" + jb + ";Pooling=False"))
            {
                dst.Open();
                _conn.BackupDatabase(dst, "main", "main");   // journal backup = schema main
                Log("SQL_JOURNAL_BACKUP", "tables=[" + Tables(dst) + "]");
            }

            Exec("DELETE FROM proj.vehicle; DELETE FROM proj.projection_meta;");
            using (var src = new SqliteConnection("Data Source=" + snap + ";Pooling=False"))
            {
                src.Open();
                src.BackupDatabase(_conn, "proj", "main");   // restore snapshot into the attached schema
            }

            Log("SQL_RESTORE", string.Format(CultureInfo.InvariantCulture, "projRows={0} watermark={1}",
                Scalar("SELECT COUNT(*) FROM proj.vehicle;"), Scalar("SELECT v FROM proj.projection_meta WHERE k='watermark';")));
        }

        private static string Tables(SqliteConnection c)
        {
            var names = new List<string>();
            using (SqliteCommand cmd = c.CreateCommand())
            {
                cmd.CommandText = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;";
                using (SqliteDataReader r = cmd.ExecuteReader())
                {
                    while (r.Read())
                    {
                        names.Add(r.GetString(0));
                    }
                }
            }

            return string.Join(",", names);
        }

        private static string ScalarOn(SqliteConnection c, string sql)
        {
            using (SqliteCommand cmd = c.CreateCommand())
            {
                cmd.CommandText = sql;
                return Convert.ToString(cmd.ExecuteScalar(), CultureInfo.InvariantCulture);
            }
        }

        private void OnAborted(object sender, EventArgs e)
        {
            if (_conn == null)
            {
                return;
            }

            if (Flag("SqliteProbe.CloseOnAbort", true))
            {
                _conn.Close();
                _conn.Dispose();
                Log("SQL_CLOSED_ON_ABORT", string.Empty);
            }
            else
            {
                Log("SQL_LEAKED_ON_ABORT", "connection intentionally left open");
            }
        }

        private void Exec(string sql)
        {
            using (SqliteCommand c = _conn.CreateCommand())
            {
                c.CommandText = sql;
                c.ExecuteNonQuery();
            }
        }

        private string Scalar(string sql)
        {
            using (SqliteCommand c = _conn.CreateCommand())
            {
                c.CommandText = sql;
                object o = c.ExecuteScalar();
                return Convert.ToString(o, CultureInfo.InvariantCulture);
            }
        }

        private static string NativeModulePath()
        {
            foreach (ProcessModule m in Process.GetCurrentProcess().Modules)
            {
                if (m.ModuleName.IndexOf("sqlite", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    return m.FileName;
                }
            }

            return "<not-found>";
        }

        private bool Flag(string key, bool fallback)
        {
            string v;
            return _cfg.TryGetValue(key, out v) ? string.Equals(v, "true", StringComparison.OrdinalIgnoreCase) : fallback;
        }

        private void Log(string evt, string data)
        {
            try
            {
                File.AppendAllText(Path.Combine(_dir, "sqlite-probe.log"),
                    DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture) + "\t" + evt + "\t" + data + Environment.NewLine, Encoding.UTF8);
            }
            catch (IOException)
            {
            }
        }

        private static Dictionary<string, string> ReadIni(string path)
        {
            var d = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            if (!File.Exists(path))
            {
                return d;
            }

            foreach (string line in File.ReadAllLines(path).Select(l => l.Trim()))
            {
                int eq = line.IndexOf('=');
                if (line.Length > 0 && line[0] != ';' && line[0] != '#' && eq > 0)
                {
                    d[line.Substring(0, eq).Trim()] = line.Substring(eq + 1).Trim();
                }
            }

            return d;
        }

        [DllImport("kernel32", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr LoadLibraryW(string path);
    }
}
