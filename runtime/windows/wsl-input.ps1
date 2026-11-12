# WSL fallback: use the Windows IME, return UTF-8 through stdout only.
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$form = New-Object System.Windows.Forms.Form
$form.Text = 'rhun - Chinese input'
$form.Size = New-Object System.Drawing.Size(680, 360)
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true
$form.MinimumSize = New-Object System.Drawing.Size(440, 260)
$label = New-Object System.Windows.Forms.Label
$label.Text = 'Windows IME input. Ctrl+Enter: insert into rhun. Esc: cancel.'
$label.Dock = 'Top'
$label.Height = 32
$inputBox = New-Object System.Windows.Forms.TextBox
$inputBox.Multiline = $true
$inputBox.AcceptsReturn = $true
$inputBox.ScrollBars = 'Vertical'
$inputBox.Dock = 'Fill'
$inputBox.MaxLength = 16384
$inputBox.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 13)
$inputBox.ImeMode = 'On'
$buttons = New-Object System.Windows.Forms.FlowLayoutPanel
$buttons.Dock = 'Bottom'
$buttons.Height = 42
$buttons.FlowDirection = 'RightToLeft'
$insert = New-Object System.Windows.Forms.Button
$insert.Text = 'Insert'
$insert.DialogResult = [System.Windows.Forms.DialogResult]::OK
$cancel = New-Object System.Windows.Forms.Button
$cancel.Text = 'Cancel'
$cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$buttons.Controls.Add($cancel)
$buttons.Controls.Add($insert)
$form.Controls.Add($inputBox)
$form.Controls.Add($label)
$form.Controls.Add($buttons)
$form.CancelButton = $cancel
$inputBox.Add_KeyDown({
    if ($_.Control -and $_.KeyCode -eq 'Enter') {
        $_.SuppressKeyPress = $true
        $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
        $form.Close()
    }
})
$form.Add_Shown({ $inputBox.Focus() })
try {
    if ($form.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        [Console]::Write($inputBox.Text.Replace([string][char]13, ''))
    }
} finally { $form.Dispose() }
