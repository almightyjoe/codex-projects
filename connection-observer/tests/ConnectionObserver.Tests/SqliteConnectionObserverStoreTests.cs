using ConnectionObserver.Core.Models;
using ConnectionObserver.Infrastructure.Storage;

namespace ConnectionObserver.Tests;

public sealed class SqliteConnectionObserverStoreTests
{
    [Fact]
    public async Task SavesAndReadsRecentConnections()
    {
        var databasePath = Path.Combine(Path.GetTempPath(), $"connection-observer-{Guid.NewGuid():N}.db");
        var store = new SqliteConnectionObserverStore(databasePath);
        var now = DateTimeOffset.UtcNow;
        var snapshot = new ConnectionSnapshot(now, new[]
        {
            new NetworkConnection("TCP", "10.0.0.2", 5000, "8.8.8.8", 443, "Established", "browser", 42, @"C:\browser.exe", null, now, now)
        });

        await store.InitializeAsync();
        await store.SaveSnapshotAsync(snapshot);
        var recent = await store.GetRecentConnectionsAsync(10);

        Assert.Single(recent);
        Assert.Equal("browser", recent[0].ProcessName);
        Assert.Equal(42, recent[0].ProcessId);
    }

    [Fact]
    public async Task StoresDnsNotes()
    {
        var databasePath = Path.Combine(Path.GetTempPath(), $"connection-observer-{Guid.NewGuid():N}.db");
        var store = new SqliteConnectionObserverStore(databasePath);

        await store.InitializeAsync();
        await store.SetNoteAsync("example.test", "203.0.113.10", "Lab host");
        var records = await store.SearchAsync("example", 10);

        Assert.Single(records);
        Assert.Equal("Lab host", records[0].Note);
    }
}
