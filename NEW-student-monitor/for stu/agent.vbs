Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
ws.Run "python.exe """ & scriptPath & "\student_agent.py""", 0, False
