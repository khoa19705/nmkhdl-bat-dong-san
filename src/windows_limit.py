"""Windows Job Object: giới hạn committed virtual memory, không phải RSS.

    Microsoft: JOBOBJECT_EXTENDED_LIMIT_INFORMATION / ProcessMemoryLimit.
    Chỉ gắn job vào tiến trình hiện tại; không đổi cấu hình toàn máy.
"""
import ctypes
from ctypes import wintypes
import os


class BasicLimit(ctypes.Structure):
    _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),
              ('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),
              ('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',wintypes.DWORD),
              ('Affinity',ctypes.c_size_t),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]


class IOCounters(ctypes.Structure):
    _fields_=[(name,ctypes.c_ulonglong) for name in ['ReadOperationCount','WriteOperationCount','OtherOperationCount',
                                                   'ReadTransferCount','WriteTransferCount','OtherTransferCount']]


class ExtendedLimit(ctypes.Structure):
    _fields_=[('BasicLimitInformation',BasicLimit),('IoInfo',IOCounters),
              ('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),
              ('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]


class ProcessCommitLimit:
    def __init__(self,mib):
        if os.name!='nt': raise NotImplementedError('Thí nghiệm giới hạn Job Object này chỉ hỗ trợ Windows.')
        if mib<32: raise ValueError('Giới hạn tối thiểu 32 MiB.')
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR]; api.CreateJobObjectW.restype=wintypes.HANDLE
        api.GetCurrentProcess.argtypes=[]; api.GetCurrentProcess.restype=wintypes.HANDLE
        api.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]; api.SetInformationJobObject.restype=wintypes.BOOL
        api.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]; api.AssignProcessToJobObject.restype=wintypes.BOOL
        api.QueryInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p]; api.QueryInformationJobObject.restype=wintypes.BOOL
        api.CloseHandle.argtypes=[wintypes.HANDLE]; api.CloseHandle.restype=wintypes.BOOL
        self.api=api; self.handle=api.CreateJobObjectW(None,None)
        if not self.handle: raise ctypes.WinError(ctypes.get_last_error())
        info=ExtendedLimit(); info.BasicLimitInformation.LimitFlags=0x100
        info.ProcessMemoryLimit=int(mib)*1024**2
        if not api.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            error=ctypes.get_last_error(); api.CloseHandle(self.handle); raise ctypes.WinError(error)
        if not api.AssignProcessToJobObject(self.handle,api.GetCurrentProcess()):
            error=ctypes.get_last_error(); api.CloseHandle(self.handle); raise ctypes.WinError(error)
        actual=self.snapshot()
        if actual['limit_bytes']!=info.ProcessMemoryLimit or not actual['enabled']:
            raise RuntimeError('Không xác nhận được giới hạn của hệ điều hành.')

    def snapshot(self):
        info=ExtendedLimit()
        if not self.api.QueryInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info),None):
            raise ctypes.WinError(ctypes.get_last_error())
        return dict(enabled=bool(info.BasicLimitInformation.LimitFlags & 0x100),
                    limit_bytes=int(info.ProcessMemoryLimit),peak_commit_bytes=int(info.PeakProcessMemoryUsed),
                    metric='Windows Job Object per-process committed virtual memory')
