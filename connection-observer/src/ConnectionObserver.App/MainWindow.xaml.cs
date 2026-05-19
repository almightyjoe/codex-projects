using System.Windows;
using ConnectionObserver.Core.Models;
using ConnectionObserver.Core.Services;
using ConnectionObserver.Infrastructure.Network;
using ConnectionObserver.Infrastructure.Storage;

namespace ConnectionObserver.App;

public partial class MainWindow : Window
{
    private readonly INetworkSnapshotService _networkSnapshotService = new SystemNetworkSnapshotService();
    private readonly ConnectionSnapshotMerger _snapshotMerger = new();
    private readonly SqliteConnectionObserverStore _store = new(AppDataPaths.DefaultDatabasePath);

    public MainWindow()
    {
        InitializeComponent();
        Loaded += async (_, _) => await RefreshConnectionsAsync();
    }

    private async void RefreshButton_Click(object sender, RoutedEventArgs e)
    {
        await RefreshConnectionsAsync();
    }

    private async Task RefreshConnectionsAsync()
    {
        RefreshButton.IsEnabled = false;
        StatusText.Text = "Refreshing network activity...";

        try
        {
            await _store.InitializeAsync();

            var snapshot = _snapshotMerger.ApplyFirstSeen(await _networkSnapshotService.CaptureAsync());
            await _store.SaveSnapshotAsync(snapshot);
            await _store.PurgeOlderThanAsync(DateTimeOffset.Now.AddDays(-AppSettings.Default.DataRetentionDays));

            TotalConnectionsText.Text = snapshot.Connections.Count.ToString();
            TcpConnectionsText.Text = snapshot.TcpCount.ToString();
            UdpConnectionsText.Text = snapshot.UdpCount.ToString();
            ConnectionsGrid.ItemsSource = snapshot.Connections
                .OrderBy(connection => connection.Protocol)
                .ThenBy(connection => connection.LocalAddress)
                .Select(ConnectionRow.FromConnection)
                .ToList();
            StatusText.Text = $"Captured {snapshot.Connections.Count} connections at {snapshot.CapturedAt.LocalDateTime:g}";
        }
        catch (Exception ex)
        {
            StatusText.Text = ex.Message;
        }
        finally
        {
            RefreshButton.IsEnabled = true;
        }
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
}
