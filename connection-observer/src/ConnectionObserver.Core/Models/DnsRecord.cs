namespace ConnectionObserver.Core.Models;

public sealed record DnsRecord(
    string Domain,
    string? IpAddress,
    DateTimeOffset FirstSeen,
    DateTimeOffset LastSeen,
    string? Note);
