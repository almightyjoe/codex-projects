namespace ConnectionObserver.Core.Models;

public sealed record NetworkConnection(
    string Protocol,
    string LocalAddress,
    int LocalPort,
    string? RemoteAddress,
    int? RemotePort,
    string State,
    string? ProcessName,
    int? ProcessId,
    string? ExecutablePath,
    string? Country,
    DateTimeOffset FirstSeen,
    DateTimeOffset LastSeen)
{
    public ConnectionKey Key => new(Protocol, LocalAddress, LocalPort, RemoteAddress, RemotePort, ProcessId);

    public bool IsLoopback =>
        LocalAddress.StartsWith("127.", StringComparison.Ordinal) ||
        LocalAddress.Equals("::1", StringComparison.Ordinal) ||
        RemoteAddress?.StartsWith("127.", StringComparison.Ordinal) == true ||
        RemoteAddress?.Equals("::1", StringComparison.Ordinal) == true;
}
