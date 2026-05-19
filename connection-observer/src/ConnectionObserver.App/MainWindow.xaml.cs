using System.Windows;
using System.Windows.Threading;
using ConnectionObserver.Core.Models;
using ConnectionObserver.Core.Services;
using ConnectionObserver.Infrastructure.Network;
using ConnectionObserver.Infrastructure.Storage;

namespace ConnectionObserver.App;

public partial class MainWindow : Window
{
    private readonly AlertEvaluator _alertEvaluator = new();
    private readonly DispatcherTimer _refreshTimer = new();
    private readonly INetworkSnapshotService _networkSnapshotService = new SystemNetworkSnapshotService();
    private readonly ConnectionSnapshotMerger _snapshotMerger = new();
    private readonly SqliteConnectionObserverStore _store = new(AppDataPaths.DefaultDatabasePath);
    private bool _isRefreshing;

    public MainWindow()
    {
        InitializeComponent();

        RuleTypeComboBox.ItemsSource = Enum.GetValues<AlertRuleType>();
        RuleTypeComboBox.SelectedItem = AlertRuleType.ProcessNameContains;
        RuleSeverityComboBox.ItemsSource = Enum.GetValues<AlertSeverity>();
        RuleSeverityComboBox.SelectedItem = AlertSeverity.Warning;

        _refreshTimer.Interval = TimeSpan.FromSeconds(AppSettings.Default.NetworkUpdateIntervalSeconds);
        _refreshTimer.Tick += async (_, _) => await RefreshConnectionsAsync();

        Loaded += async (_, _) =>
        {
            await _store.InitializeAsync();
            await RefreshAllAsync();
        };
        Closed += (_, _) => _refreshTimer.Stop();
    }

    private async void RefreshButton_Click(object sender, RoutedEventArgs e)
    {
        await RefreshConnectionsAsync();
    }

    private void AutoRefreshCheckBox_Changed(object sender, RoutedEventArgs e)
    {
        if (AutoRefreshCheckBox.IsChecked == true)
        {
            _refreshTimer.Start();
            StatusText.Text = $"Auto refresh every {AppSettings.Default.NetworkUpdateIntervalSeconds} seconds";
        }
        else
        {
            _refreshTimer.Stop();
            StatusText.Text = "Auto refresh paused";
        }
    }

    private async void ReloadHistoryButton_Click(object sender, RoutedEventArgs e)
    {
        await LoadHistoryAsync();
    }

    private async void ReloadAlertsButton_Click(object sender, RoutedEventArgs e)
    {
        await LoadAlertsAsync();
    }

    private async void SaveDnsNoteButton_Click(object sender, RoutedEventArgs e)
    {
        var domain = DnsDomainTextBox.Text.Trim();
        var note = DnsNoteTextBox.Text.Trim();

        if (string.IsNullOrWhiteSpace(domain) || string.IsNullOrWhiteSpace(note))
        {
            StatusText.Text = "Domain and note are required.";
            return;
        }

        var ipAddress = string.IsNullOrWhiteSpace(DnsIpTextBox.Text) ? null : DnsIpTextBox.Text.Trim();
        await _store.SetNoteAsync(domain, ipAddress, note);
        DnsDomainTextBox.Clear();
        DnsIpTextBox.Clear();
        DnsNoteTextBox.Clear();
        await LoadDnsNotesAsync();
        StatusText.Text = $"Saved note for {domain}";
    }

    private async void AddRuleButton_Click(object sender, RoutedEventArgs e)
    {
        var ruleType = (AlertRuleType?)RuleTypeComboBox.SelectedItem ?? AlertRuleType.ProcessNameContains;
        var severity = (AlertSeverity?)RuleSeverityComboBox.SelectedItem ?? AlertSeverity.Warning;
        var condition = RuleConditionTextBox.Text.Trim();

        if (ruleType != AlertRuleType.NewExternalConnection && string.IsNullOrWhiteSpace(condition))
        {
            StatusText.Text = "Rule condition is required.";
            return;
        }

        var rule = new AlertRule(Guid.NewGuid(), ruleType, condition, severity, true);
        await _store.SaveRuleAsync(rule);
        RuleConditionTextBox.Clear();
        await LoadRulesAsync();
        StatusText.Text = "Rule saved.";
    }

    private async Task RefreshAllAsync()
    {
        await RefreshConnectionsAsync();
        await LoadHistoryAsync();
        await LoadDnsNotesAsync();
        await LoadRulesAsync();
        await LoadAlertsAsync();
    }

    private async Task RefreshConnectionsAsync()
    {
        if (_isRefreshing)
        {
            return;
        }

        _isRefreshing = true;
        RefreshButton.IsEnabled = false;
        StatusText.Text = "Refreshing network activity...";

        try
        {
            var snapshot = _snapshotMerger.ApplyFirstSeen(await _networkSnapshotService.CaptureAsync());
            await _store.SaveSnapshotAsync(snapshot);
            await _store.PurgeOlderThanAsync(DateTimeOffset.Now.AddDays(-AppSettings.Default.DataRetentionDays));
            await EvaluateAlertsAsync(snapshot);

            var connectionRows = snapshot.Connections
                .OrderBy(connection => connection.Protocol)
                .ThenBy(connection => connection.LocalAddress)
                .Select(ConnectionRow.FromConnection)
                .ToList();

            TotalConnectionsText.Text = snapshot.Connections.Count.ToString();
            TcpConnectionsText.Text = snapshot.TcpCount.ToString();
            UdpConnectionsText.Text = snapshot.UdpCount.ToString();
            ConnectionsGrid.ItemsSource = connectionRows;

            await LoadHistoryAsync();
            await LoadAlertsAsync();
            StatusText.Text = $"Captured {snapshot.Connections.Count} connections at {snapshot.CapturedAt.LocalDateTime:g}";
        }
        catch (Exception ex)
        {
            StatusText.Text = ex.Message;
        }
        finally
        {
            RefreshButton.IsEnabled = true;
            _isRefreshing = false;
        }
    }

    private async Task EvaluateAlertsAsync(ConnectionSnapshot snapshot)
    {
        _alertEvaluator.ForgetInactiveConnections(snapshot.Connections);
        var rules = await _store.GetRulesAsync();
        var alerts = _alertEvaluator.Evaluate(snapshot, rules);
        foreach (var alert in alerts)
        {
            await _store.SaveAlertAsync(alert);
        }
    }

    private async Task LoadHistoryAsync()
    {
        var recent = await _store.GetRecentConnectionsAsync(500);
        HistoryGrid.ItemsSource = recent.Select(ConnectionRow.FromConnection).ToList();
    }

    private async Task LoadDnsNotesAsync()
    {
        var records = await _store.SearchAsync(null, 500);
        DnsGrid.ItemsSource = records.Select(DnsRow.FromRecord).ToList();
    }

    private async Task LoadRulesAsync()
    {
        var rules = await _store.GetRulesAsync();
        RulesGrid.ItemsSource = rules.Select(RuleRow.FromRule).ToList();
    }

    private async Task LoadAlertsAsync()
    {
        var alerts = await _store.GetRecentAlertsAsync(500);
        AlertCountText.Text = alerts.Count.ToString();
        AlertsGrid.ItemsSource = alerts.Select(AlertRow.FromAlert).ToList();
    }

    private sealed record ConnectionRow(
        string Protocol,
        string LocalEndpoint,
        string RemoteEndpoint,
        string State,
        string ProcessName,
        string ProcessId,
        string LastSeen)
    {
        public static ConnectionRow FromConnection(NetworkConnection connection)
        {
            var remote = connection.RemoteAddress is null
                ? string.Empty
                : $"{connection.RemoteAddress}:{connection.RemotePort}";

            return new ConnectionRow(
                connection.Protocol,
                $"{connection.LocalAddress}:{connection.LocalPort}",
                remote,
                connection.State,
                connection.ProcessName ?? string.Empty,
                connection.ProcessId?.ToString() ?? string.Empty,
                connection.LastSeen.ToLocalTime().ToString("g"));
        }
    }

    private sealed record DnsRow(string Domain, string IpAddress, string Note, string LastSeen)
    {
        public static DnsRow FromRecord(DnsRecord record)
        {
            return new DnsRow(
                record.Domain,
                record.IpAddress ?? string.Empty,
                record.Note ?? string.Empty,
                record.LastSeen.ToLocalTime().ToString("g"));
        }
    }

    private sealed record RuleRow(string Type, string Condition, string Severity, bool IsEnabled)
    {
        public static RuleRow FromRule(AlertRule rule)
        {
            return new RuleRow(rule.Type.ToString(), rule.Condition, rule.Severity.ToString(), rule.IsEnabled);
        }
    }

    private sealed record AlertRow(string Severity, string Description, string ProcessName, string RemoteEndpoint, string CreatedAt)
    {
        public static AlertRow FromAlert(AlertEvent alert)
        {
            var remote = alert.Connection.RemoteAddress is null
                ? string.Empty
                : $"{alert.Connection.RemoteAddress}:{alert.Connection.RemotePort}";

            return new AlertRow(
                alert.Severity.ToString(),
                alert.Description,
                alert.Connection.ProcessName ?? string.Empty,
                remote,
                alert.CreatedAt.ToLocalTime().ToString("g"));
        }
    }
}
