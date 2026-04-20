' VideoLoader - Lanceur silencieux
' Lance le serveur sans fenetre noire, ouvre le navigateur par defaut

Dim fso, scriptDir, oShell
Set fso = CreateObject("Scripting.FileSystemObject")
Set oShell = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Verifie si le serveur tourne deja
Set objWMI = GetObject("winmgmts:\\.\root\cimv2")
Set processes = objWMI.ExecQuery("SELECT * FROM Win32_Process WHERE CommandLine LIKE '%uvicorn%server%'")

If processes.Count > 0 Then
    oShell.Run "http://localhost:8000", 1, False
    WScript.Quit
End If

' Lance le serveur en arriere-plan
oShell.CurrentDirectory = scriptDir
oShell.Run "cmd /c python -m uvicorn server:app --port 8000 > """ & scriptDir & "\videoloader.log"" 2>&1", 0, False

' Attend que le serveur soit pret (max 15 secondes)
Dim i
For i = 1 To 15
    WScript.Sleep 1000
    On Error Resume Next
    Dim http
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.Open "GET", "http://localhost:8000", False
    http.Send
    If http.Status = 200 Or http.Status = 304 Then
        Exit For
    End If
    On Error GoTo 0
Next

' Ouvre dans le navigateur par defaut
oShell.Run "http://localhost:8000", 1, False
