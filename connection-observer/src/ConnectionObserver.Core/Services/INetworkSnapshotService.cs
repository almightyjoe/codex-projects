using ConnectionObserver.Core.Models;

namespace ConnectionObserver.Core.Services;

public interface INetworkSnapshotService
{
    Task<ConnectionSnapshot> CaptureAsync(CancellationToken cancellationToken = default);
}
