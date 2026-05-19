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
    DateTimeOffset LastSeen);
