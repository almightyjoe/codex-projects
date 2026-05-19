using System.Net.NetworkInformation;
using ConnectionObserver.Core.Models;
using ConnectionObserver.Core.Services;

namespace ConnectionObserver.Infrastructure.Network;

public sealed class SystemNetworkSnapshotService : INetworkSnapshotService
{
    private readonly WindowsConnectionOwnerProvider _ownerProvider = new();

    public Task<ConnectionSnapshot> CaptureAsync(CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();

        var capturedAt = DateTimeOffset.Now;
        var properties = IPGlobalProperties.GetIPGlobalProperties();
        var owners = _ownerProvider.GetOwners();
        var tcpOwners = owners
            .Where(owner => owner.Protocol == "TCP")
            .ToDictionary(owner => (owner.LocalAddress, owner.LocalPort, owner.RemoteAddress, owner.RemotePort));
        var udpOwners = owners
            .Where(owner => owner.Protocol == "UDP")
            .GroupBy(owner => (owner.LocalAddress, owner.LocalPort))
            .ToDictionary(group => group.Key, group => group.First());
        var processCache = new Dictionary<int, ProcessInfo?>();
        var connections = new List<NetworkConnection>();

        foreach (var connection in properties.GetActiveTcpConnections())
        {
            tcpOwners.TryGetValue((
                connection.LocalEndPoint.Address.ToString(),
                connection.LocalEndPoint.Port,
                connection.RemoteEndPoint.Address.ToString(),
                connection.RemoteEndPoint.Port), out var owner);
            var process = GetProcessInfo(owner?.ProcessId, processCache);

            connections.Add(new NetworkConnection(
                Protocol: "TCP",
                LocalAddress: connection.LocalEndPoint.Address.ToString(),
                LocalPort: connection.LocalEndPoint.Port,
                RemoteAddress: connection.RemoteEndPoint.Address.ToString(),
                RemotePort: connection.RemoteEndPoint.Port,
                State: connection.State.ToString(),
                ProcessName: process?.ProcessName,
                ProcessId: owner?.ProcessId,
                ExecutablePath: process?.ExecutablePath,
                Country: null,
                FirstSeen: capturedAt,
                LastSeen: capturedAt));
        }

        foreach (var listener in properties.GetActiveUdpListeners())
        {
            udpOwners.TryGetValue((listener.Address.ToString(), listener.Port), out var owner);
            var process = GetProcessInfo(owner?.ProcessId, processCache);

            connections.Add(new NetworkConnection(
                Protocol: "UDP",
                LocalAddress: listener.Address.ToString(),
                LocalPort: listener.Port,
                RemoteAddress: null,
                RemotePort: null,
                State: "Listening",
                ProcessName: process?.ProcessName,
                ProcessId: owner?.ProcessId,
                ExecutablePath: process?.ExecutablePath,
                Country: null,
                FirstSeen: capturedAt,
                LastSeen: capturedAt));
        }

        return Task.FromResult(new ConnectionSnapshot(capturedAt, connections));
    }

    private ProcessInfo? GetProcessInfo(int? processId, Dictionary<int, ProcessInfo?> processCache)
    {
        if (processId is null)
        {
            return null;
        }

        if (!processCache.TryGetValue(processId.Value, out var processInfo))
        {
            processInfo = _ownerProvider.TryGetProcessInfo(processId.Value);
            processCache[processId.Value] = processInfo;
        }

        return processInfo;
    }
}
