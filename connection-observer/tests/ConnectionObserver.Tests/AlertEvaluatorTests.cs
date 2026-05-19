using ConnectionObserver.Core.Models;
using ConnectionObserver.Core.Services;

namespace ConnectionObserver.Tests;

public sealed class AlertEvaluatorTests
{
    [Fact]
    public void MatchesProcessNameRule()
    {
        var now = DateTimeOffset.UtcNow;
        var snapshot = new ConnectionSnapshot(now, new[]
        {
            new NetworkConnection("TCP", "10.0.0.2", 5000, "8.8.8.8", 443, "Established", "browser", 42, null, null, now, now)
        });
        var rules = new[]
        {
            new AlertRule(Guid.NewGuid(), AlertRuleType.ProcessNameContains, "browse", AlertSeverity.Warning, true)
        };

        var alerts = new AlertEvaluator().Evaluate(snapshot, rules);

        Assert.Single(alerts);
        Assert.Equal(AlertSeverity.Warning, alerts[0].Severity);
    }
}
