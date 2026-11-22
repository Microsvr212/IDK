using System.Diagnostics;
using System.Text.Json;
using Microsoft.Win32;

namespace NovaFortniteOptimizer;

internal static class Program
{
    [STAThread]
    static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
    }
}

public sealed class MainForm : Form
{
    private readonly string stateDir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "NOVAOptimizer");
    private readonly string stateFile;
    private readonly Label status = new();
    private readonly Label fortnite = new();
    private readonly Label latency = new();
    private readonly Dictionary<string, object?> original = new();

    public MainForm()
    {
        stateFile = Path.Combine(stateDir, "state.json");
        Directory.CreateDirectory(stateDir);
        LoadState();

        Text = "NOVA • Fortnite Optimizer";
        Size = new Size(850, 620);
        MinimumSize = new Size(760, 540);
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(13, 16, 25);
        ForeColor = Color.White;
        Font = new Font("Segoe UI", 10);

        var header = new Label { Text = "NOVA", Font = new Font("Segoe UI", 28, FontStyle.Bold),
            ForeColor = Color.FromArgb(100, 190, 255), AutoSize = true, Location = new Point(28, 20) };
        var sub = new Label { Text = "FORTNITE OPTIMIZER  |  SAFE • REVERSIBLE • PORTABLE",
            ForeColor = Color.Silver, AutoSize = true, Location = new Point(33, 72) };
        Controls.Add(header); Controls.Add(sub);

        var panel = new Panel { Location = new Point(28, 115), Size = new Size(775, 105),
            BackColor = Color.FromArgb(24, 30, 44) };
        fortnite.SetBounds(20, 17, 350, 28);
        latency.SetBounds(20, 53, 500, 25);
        status.SetBounds(500, 17, 250, 60);
        status.ForeColor = Color.LightGreen;
        panel.Controls.Add(fortnite); panel.Controls.Add(latency); panel.Controls.Add(status);
        Controls.Add(panel);

        AddTweak("Windows Game Mode", "Turns on Windows Game Mode for your account.",
            245, () => SetDword(@"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1),
            () => RestoreDword(@"Software\Microsoft\GameBar", "AutoGameModeEnabled"));
        AddTweak("Background Game DVR capture", "Turns off background game recording. You can still record manually in supported apps.",
            335, () => SetDword(@"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0),
            () => RestoreDword(@"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled"));
        AddTweak("Windows visual effects", "Turns off transparency effects for a lighter desktop.",
            425, () => SetDword(@"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", 0),
            () => RestoreDword(@"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency"));

        var refresh = MakeButton("Refresh status", 28, 515, 145, Color.FromArgb(55, 75, 105));
        refresh.Click += (_, _) => RefreshStatus();
        var undoAll = MakeButton("UNDO ALL", 185, 515, 145, Color.FromArgb(145, 65, 65));
        undoAll.Click += (_, _) => { RestoreAll(); RefreshStatus(); };
        Controls.Add(refresh); Controls.Add(undoAll);

        RefreshStatus();
        var timer = new System.Windows.Forms.Timer { Interval = 2500 };
        timer.Tick += (_, _) => RefreshStatus();
        timer.Start();
    }

    private void AddTweak(string title, string description, int y, Action apply, Action undo)
    {
        var p = new Panel { Location = new Point(28, y), Size = new Size(775, 78),
            BackColor = Color.FromArgb(24, 30, 44) };
        var t = new Label { Text = title, Font = new Font("Segoe UI", 11, FontStyle.Bold),
            AutoSize = true, Location = new Point(15, 9) };
        var d = new Label { Text = description, ForeColor = Color.Silver,
            AutoSize = true, Location = new Point(15, 39) };
        var a = MakeButton("APPLY", 560, 18, 88, Color.FromArgb(35, 125, 95));
        var u = MakeButton("UNDO", 658, 18, 88, Color.FromArgb(145, 65, 65));
        a.Click += (_, _) => { try { apply(); status.Text = "Applied: " + title; } catch (Exception ex) { MessageBox.Show(ex.Message, "NOVA"); } };
        u.Click += (_, _) => { try { undo(); status.Text = "Restored: " + title; } catch (Exception ex) { MessageBox.Show(ex.Message, "NOVA"); } };
        p.Controls.AddRange(new Control[] { t, d, a, u }); Controls.Add(p);
    }

    private Button MakeButton(string text, int x, int y, int w, Color color)
    {
        return new Button { Text = text, Location = new Point(x, y), Size = new Size(w, 38),
            FlatStyle = FlatStyle.Flat, BackColor = color, ForeColor = Color.White,
            Cursor = Cursors.Hand };
    }

    private void SetDword(string key, string name, int value)
    {
        using var k = Registry.CurrentUser.CreateSubKey(key);
        var id = key + "|" + name;
        if (!original.ContainsKey(id))
        {
            object? old = k?.GetValue(name);
            original[id] = old == null ? null : Convert.ToInt32(old);
            SaveState();
        }
        k!.SetValue(name, value, RegistryValueKind.DWord);
    }

    private void RestoreDword(string key, string name)
    {
        var id = key + "|" + name;
        if (!original.TryGetValue(id, out var old)) return;
        using var k = Registry.CurrentUser.CreateSubKey(key);
        if (old == null) k?.DeleteValue(name, false);
        else k?.SetValue(name, Convert.ToInt32(old), RegistryValueKind.DWord);
        original.Remove(id);
        SaveState();
    }

    private void RestoreAll()
    {
        foreach (var id in original.Keys.ToList())
        {
            var parts = id.Split('|');
            RestoreDword(parts[0], parts[1]);
        }
        status.Text = "All saved settings restored.";
    }

    private void SaveState()
    {
        File.WriteAllText(stateFile, JsonSerializer.Serialize(original));
    }

    private void LoadState()
    {
        try
        {
            if (File.Exists(stateFile))
            {
                var data = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(File.ReadAllText(stateFile));
                if (data != null)
                    foreach (var pair in data)
                        original[pair.Key] = pair.Value.ValueKind == JsonValueKind.Null ? null : pair.Value.GetInt32();
            }
        }
        catch { }
    }

    private void RefreshStatus()
    {
        bool running = Process.GetProcessesByName("FortniteClient-Win64-Shipping").Length > 0;
        fortnite.Text = running ? "FORTNITE: RUNNING" : "FORTNITE: NOT DETECTED";
        fortnite.ForeColor = running ? Color.LightGreen : Color.Silver;
        latency.Text = "Internet check: " + GetPing();
    }

    private string GetPing()
    {
        try
        {
            using var ping = new System.Net.NetworkInformation.Ping();
            var reply = ping.Send("1.1.1.1", 1200);
            return reply.Status == System.Net.NetworkInformation.IPStatus.Success
                ? $"Cloudflare response: {reply.RoundtripTime} ms (not Fortnite server ping)"
                : "No response";
        }
        catch { return "Unavailable"; }
    }
}
