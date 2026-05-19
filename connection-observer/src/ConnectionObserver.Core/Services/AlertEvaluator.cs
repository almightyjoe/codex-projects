using ConnectionObserver.Core.Models;

namespace ConnectionObserver.Core.Services;

public sealed class AlertEvaluator
{
    private readonly HashSet<string> _raisedAlertKeys = new(StringComparer.OrdinalIgnoreCase);

    public IReadOnlyList<AlertEvent> Evaluate(ConnectionSnapshot snapshot, IReadOnlyCollection<AlertRule> rules)
    {
        var enabledRules = rules.Where(rule => rule.IsEnabled).ToArray();
        if (enabledRules.Length == 0)
        {
            return Array.Empty<AlertEvent>();
        }

        var alerts = new List<AlertEvent>();

        foreach (var connection in snapshot.Connections)
        {
            foreach (var rule in enabledRules)
            {
                if (!Matches(rule, connection))
                {
                    continue;
                }

                var alertKey = CreateAlertKey(rule, connection);
                if (!_raisedAlertKeys.Add(alertKey))
                {
                    continue;
                }

                alerts.Add(new AlertEvent(
                    Guid.NewGuid(),
                    rule.Id,
                    rule.Severity,
                    Describe(rule, connection),
                    connection,
                    snapshot.CapturedAt));
            }
        }

        return alerts;
    }

    public void ForgetInactiveConnections(IReadOnlyCollection<NetworkConnection> activeConnections)
    {
        var activeConnectionKeys = activeConnections
            .Select(connection => connection.Key.ToString())
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        foreach (var raisedKey in _raisedAlertKeys.ToArray())
        {
            var separatorIndex = raisedKey.IndexOf('|');
            if (separatorIndex < 0 || !activeConnectionKeys.Contains(raisedKey[(separatorIndex + 1)..]))
            {
                _raisedAlertKeys.Remove(raisedKey);
            }
        }
    }

    private static bool Matches(AlertRule rule, NetworkConnection connection)
    {
        return rule.Type switch
        {
            AlertRuleType.RemoteAddressContains => Contains(connection.RemoteAddress, rule.Condition),
            AlertRuleType.ProcessNameContains => Contains(connection.ProcessName, rule.Condition),
            AlertRuleType.CountryEquals => string.Equals(connection.Country, rule.Condition, StringComparison.OrdinalIgnoreCase),
            AlertRuleType.NewExternalConnection => connection.RemoteAddress is not null && !connection.IsLoopback,
            _ => false
        };
    }

    private static string Describe(AlertRule rule, NetworkConnection connection)
    {
        return rule.Type switch
        {
            AlertRuleType.NewExternalConnection => $"New external {connection.Protocol} connection to {connection.RemoteAddress}:{connection.RemotePort}",
            _ => $"{rule.Type} matched {rule.Condition}"
        };
    }

    private static bool Contains(string? value, string condition)
    {
        return value?.Contains(condition, StringComparison.OrdinalIgnoreCase) == true;
    }

    private static string CreateAlertKey(AlertRule rule, NetworkConnection connection)
    {
        return $"{rule.Id}|{connection.Key}";
    }
}
