using System.Net.NetworkInformation;
using ConnectionObserver.Core.Models;
using ConnectionObserver.Core.Services;

namespace ConnectionObserver.Infrastructure.Network;

public sealed class SystemNetworkSnapshotService : INetworkSnapshotService
{
    public Task<ConnectionSnapshot> CaptureAsync(CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();

        var capturedAt = DateTimeOffset.Now;
        var properties = IPGlobalProperties.GetIPGlobalProperties();
        var connections = new List<NetworkConnection>();

        foreach (var connection in properties.GetActiveTcpConnections())
        {
            connections.Add(new NetworkConnection(
                Protocol: "TCP",
                LocalAddress: connection.LocalEndPoint.Address.ToString(),
                LocalPort: connection.LocalEndPoint.Port,
                RemoteAddress: connection.RemoteEndPoint.Address.ToString(),
                RemotePort: connection.RemoteEndPoint.Port,
                State: connection.State.ToString(),
                ProcessName: null,
                ProcessId: null,
                ExecutablePath: null,
                Country: null,
                FirstSeen: capturedAt,
                LastSeen: capturedAt));
        }

        foreach (var listener in properties.GetActiveUdpListeners())
        {
            connections.Add(new NetworkConnection(
                Protocol: "UDP",
                LocalAddress: listener.Address.ToString(),
                LocalPort: listener.Port,
                RemoteAddress: null,
                RemotePort: null,
                State: "Listening",
                ProcessName: null,
                ProcessId: null,
                ExecutablePath: null,
                Country: null,
                FirstSeen: capturedAt,
                LastSeen: capturedAt));
        }

        return Task.FromResult(new ConnectionSnapshot(capturedAt, connections));
    }
}
