// =====================================================================================
// DISPOSABLE PHASE 0 FEASIBILITY PROBE — NOT LSAX PRODUCTION CODE. DO NOT SHIP OR REUSE.
// P-DB-01: can Microsoft.Data.Sqlite + native e_sqlite3 load inside SHVDN's shadow-copied script AppDomain,
// survive repeated domain reloads (console `Reload`, SP save load), and commit durably within tick budget?
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
            }
            catch (Exception ex)
            {
                Log("SQL_FAIL", ex.GetType().FullName + ": " + ex.Message + " inner=" + (ex.InnerException != null ? ex.InnerException.Message : "-"));
            }

            Aborted += OnAborted;
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
