using ConnectionObserver.Core.Models;

namespace ConnectionObserver.Core.Services;

public sealed class ConnectionSnapshotMerger
{
    private readonly Dictionary<ConnectionKey, DateTimeOffset> _firstSeenByConnection = new();

    public ConnectionSnapshot ApplyFirstSeen(ConnectionSnapshot snapshot)
    {
        var merged = snapshot.Connections
            .Select(connection =>
            {
                if (!_firstSeenByConnection.TryGetValue(connection.Key, out var firstSeen))
                {
                    firstSeen = connection.FirstSeen;
                    _firstSeenByConnection[connection.Key] = firstSeen;
                }

                return connection with { FirstSeen = firstSeen };
            })
            .ToArray();

        var activeKeys = merged.Select(connection => connection.Key).ToHashSet();
        foreach (var staleKey in _firstSeenByConnection.Keys.Where(key => !activeKeys.Contains(key)).ToArray())
        {
            _firstSeenByConnection.Remove(staleKey);
        }

        return snapshot with { Connections = merged };
    }
}
