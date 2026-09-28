// Disposable check (not LSAX code): runs the exact D-DB-4 BackupDatabase calls used by P-DB-01.
using System; using System.IO; using System.Collections.Generic; using Microsoft.Data.Sqlite;
class P {
  static string Tables(SqliteConnection c){var l=new List<string>();using var cmd=c.CreateCommand();cmd.CommandText="SELECT name FROM sqlite_master WHERE type='table' ORDER BY name";using var r=cmd.ExecuteReader();while(r.Read())l.Add(r.GetString(0));return string.Join(",",l);}
  static object S(SqliteConnection c,string q){using var cmd=c.CreateCommand();cmd.CommandText=q;return cmd.ExecuteScalar();}
  static void X(SqliteConnection c,string q){using var cmd=c.CreateCommand();cmd.CommandText=q;cmd.ExecuteNonQuery();}
  static int Main(){
    string d=Path.Combine(Path.GetTempPath(),"lsaxbk"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(d);
    using var live=new SqliteConnection("Data Source="+Path.Combine(d,"p0.db")+";Pooling=False");live.Open();
    X(live,"PRAGMA journal_mode=WAL;PRAGMA synchronous=FULL;CREATE TABLE probe_row(id INTEGER PRIMARY KEY, utc TEXT)");
    X(live,$"ATTACH DATABASE '{Path.Combine(d,"p0_proj.db")}' AS proj;PRAGMA proj.journal_mode=WAL;PRAGMA proj.synchronous=NORMAL;CREATE TABLE proj.projection_meta(k TEXT PRIMARY KEY, v TEXT);CREATE TABLE proj.vehicle(id INTEGER PRIMARY KEY, utc TEXT)");
    for(int i=1;i<=20;i++){X(live,$"INSERT INTO main.probe_row(utc) VALUES('{i}')");X(live,$"INSERT OR REPLACE INTO proj.vehicle VALUES({i},'{i}');INSERT OR REPLACE INTO proj.projection_meta VALUES('watermark','{i}')");}
    bool ok=true;
    using(var s=new SqliteConnection("Data Source="+Path.Combine(d,"snap.db")+";Pooling=False")){s.Open();live.BackupDatabase(s,"main","proj");var t=Tables(s);Console.WriteLine("SNAPSHOT tables=["+t+"] watermark="+S(s,"SELECT v FROM projection_meta WHERE k='watermark'"));ok&=t=="projection_meta,vehicle";}
    using(var j=new SqliteConnection("Data Source="+Path.Combine(d,"jb.db")+";Pooling=False")){j.Open();live.BackupDatabase(j,"main","main");var t=Tables(j);Console.WriteLine("JOURNAL_BACKUP tables=["+t+"]");ok&=t=="probe_row";}
    X(live,"DELETE FROM proj.vehicle;DELETE FROM proj.projection_meta");
    using(var s=new SqliteConnection("Data Source="+Path.Combine(d,"snap.db")+";Pooling=False")){s.Open();s.BackupDatabase(live,"proj","main");}
    var rows=S(live,"SELECT COUNT(*) FROM proj.vehicle");var wm=S(live,"SELECT v FROM proj.projection_meta WHERE k='watermark'");
    Console.WriteLine($"RESTORE projRows={rows} watermark={wm} sqlite={S(live,"SELECT sqlite_version()")} main.sync={S(live,"PRAGMA main.synchronous")} proj.sync={S(live,"PRAGMA proj.synchronous")}");
    ok&=Convert.ToInt64(rows)==20 && (string)wm=="20";
    Console.WriteLine("RESULT: "+(ok?"PASS":"FAIL"));return ok?0:1;}
}
