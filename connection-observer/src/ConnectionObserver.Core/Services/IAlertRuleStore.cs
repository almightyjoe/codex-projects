using ConnectionObserver.Core.Models;

namespace ConnectionObserver.Core.Services;

public interface IAlertRuleStore
{
    Task<IReadOnlyList<AlertRule>> GetRulesAsync(CancellationToken cancellationToken = default);

    Task SaveRuleAsync(AlertRule rule, CancellationToken cancellationToken = default);

    Task SaveAlertAsync(AlertEvent alertEvent, CancellationToken cancellationToken = default);

    Task<IReadOnlyList<AlertEvent>> GetRecentAlertsAsync(int limit, CancellationToken cancellationToken = default);
}
