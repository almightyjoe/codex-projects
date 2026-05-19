namespace ConnectionObserver.Core.Models;

public sealed record ConnectionKey(
    string Protocol,
    string LocalAddress,
    int LocalPort,
    string? RemoteAddress,
    int? RemotePort,
    int? ProcessId);
