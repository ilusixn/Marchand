#include <windows.h>
#include <wchar.h>

static void fail(const wchar_t *msg) {
    MessageBoxW(NULL, msg, L"Marchand Studio", MB_OK | MB_ICONERROR);
}

int WINAPI wWinMain(HINSTANCE h, HINSTANCE p, PWSTR cmd, int show) {
    wchar_t exe[MAX_PATH], dir[MAX_PATH], py[MAX_PATH], app[MAX_PATH], line[2 * MAX_PATH + 16], msg[2 * MAX_PATH + 200];
    GetModuleFileNameW(NULL, exe, MAX_PATH);
    wcscpy(dir, exe);
    wchar_t *slash = wcsrchr(dir, L'\\');
    if (slash) *slash = 0;
    swprintf(py, MAX_PATH, L"%ls\\python\\pythonw.exe", dir);
    swprintf(app, MAX_PATH, L"%ls\\app\\app.py", dir);
    if (GetFileAttributesW(py) == INVALID_FILE_ATTRIBUTES || GetFileAttributesW(app) == INVALID_FILE_ATTRIBUTES) {
        swprintf(msg, 2 * MAX_PATH + 200, L"Marchand Studio files are missing in:\n%ls\n\nRun the installer again.", dir);
        fail(msg);
        return 1;
    }
    SetEnvironmentVariableW(L"MARCHAND_NO_PIP", L"1");
    swprintf(line, 2 * MAX_PATH + 16, L"\"%ls\" \"%ls\"", py, app);
    wchar_t work[MAX_PATH];
    swprintf(work, MAX_PATH, L"%ls\\app", dir);
    STARTUPINFOW si = { sizeof(si) };
    PROCESS_INFORMATION pi;
    if (!CreateProcessW(NULL, line, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, work, &si, &pi)) {
        fail(L"Could not start Marchand Studio.");
        return 1;
    }
    DWORD r = WaitForSingleObject(pi.hProcess, 4000);
    if (r == WAIT_OBJECT_0) {
        DWORD code = 0;
        GetExitCodeProcess(pi.hProcess, &code);
        if (code != 0) {
            fail(L"Marchand Studio stopped right after starting.\n\nDetails are in:\n%USERPROFILE%\\.marchand\\app.log");
            return 1;
        }
    }
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return 0;
}
