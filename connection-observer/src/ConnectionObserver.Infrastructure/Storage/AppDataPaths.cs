namespace ConnectionObserver.Infrastructure.Storage;

public static class AppDataPaths
{
    public static string DefaultDatabasePath
    {
        get
        {
            var root = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            var directory = Path.Combine(root, "ConnectionObserver");
            Directory.CreateDirectory(directory);
            return Path.Combine(directory, "connection-observer.db");
        }
    }
}
