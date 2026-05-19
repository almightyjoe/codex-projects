using ConnectionObserver.Core.Models;

namespace ConnectionObserver.Core.Services;

public interface IConnectionHistoryStore
{
    Task InitializeAsync(CancellationToken cancellationToken = default);

    Task SaveSnapshotAsync(ConnectionSnapshot snapshot, CancellationToken cancellationToken = default);

    Task<IReadOnlyList<NetworkConnection>> GetRecentConnectionsAsync(int limit, CancellationToken cancellationToken = default);

    Task PurgeOlderThanAsync(DateTimeOffset cutoff, CancellationToken cancellationToken = default);
}
