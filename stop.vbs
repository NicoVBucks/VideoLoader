' VideoLoader - Arret du serveur

Dim objWMI, processes, proc
Set objWMI = GetObject("winmgmts:\\.\root\cimv2")
Set processes = objWMI.ExecQuery("SELECT * FROM Win32_Process WHERE CommandLine LIKE '%uvicorn%server%'")

Dim count
count = 0

For Each proc In processes
    proc.Terminate()
    count = count + 1
Next

If count > 0 Then
    MsgBox "VideoLoader arrete.", 64, "VideoLoader"
Else
    MsgBox "VideoLoader n'etait pas en cours d'execution.", 64, "VideoLoader"
End If
