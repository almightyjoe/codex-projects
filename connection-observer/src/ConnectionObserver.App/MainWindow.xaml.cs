using System.Windows;
using ConnectionObserver.Core.Models;
using ConnectionObserver.Core.Services;
using ConnectionObserver.Infrastructure.Network;

namespace ConnectionObserver.App;

public partial class MainWindow : Window
{
    private readonly INetworkSnapshotService _networkSnapshotService = new SystemNetworkSnapshotService();

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

        try
        {
            var snapshot = await _networkSnapshotService.CaptureAsync();
            TotalConnectionsText.Text = snapshot.Connections.Count.ToString();
            TcpConnectionsText.Text = snapshot.TcpCount.ToString();
            UdpConnectionsText.Text = snapshot.UdpCount.ToString();
            ConnectionsGrid.ItemsSource = snapshot.Connections
                .OrderBy(connection => connection.Protocol)
                .ThenBy(connection => connection.LocalAddress)
                .Select(ConnectionRow.FromConnection)
                .ToList();
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
                connection.LastSeen.ToLocalTime().ToString("g"));
        }
    }
}
