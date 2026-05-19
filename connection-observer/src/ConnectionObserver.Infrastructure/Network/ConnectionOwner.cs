namespace ConnectionObserver.Infrastructure.Network;

internal sealed record ConnectionOwner(
    string Protocol,
    string LocalAddress,
    int LocalPort,
    string? RemoteAddress,
    int? RemotePort,
    int ProcessId);
