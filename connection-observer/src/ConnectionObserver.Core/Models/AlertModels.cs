namespace ConnectionObserver.Core.Models;

public enum AlertSeverity
{
    Info,
    Warning,
    Critical
}

public enum AlertRuleType
{
    RemoteAddressContains,
    ProcessNameContains,
    CountryEquals,
    NewExternalConnection
}

public sealed record AlertRule(
    Guid Id,
    AlertRuleType Type,
    string Condition,
    AlertSeverity Severity,
    bool IsEnabled);

public sealed record AlertEvent(
    Guid Id,
    Guid? RuleId,
    AlertSeverity Severity,
    string Description,
    NetworkConnection Connection,
    DateTimeOffset CreatedAt);
