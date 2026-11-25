//go:build windows

package launcher

import "golang.org/x/sys/windows"

// New descendants inherit this private ACL, including credentials written by
// Node (POSIX permission bits alone do not establish privacy on Windows).
func restrictDirectory(path string) error {
	user, err := windows.GetCurrentProcessToken().GetTokenUser()
	if err != nil {
		return err
	}
	entries := "(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;" + user.User.Sid.String() + ")"
	existing, err := windows.GetNamedSecurityInfo(path, windows.SE_FILE_OBJECT, windows.DACL_SECURITY_INFORMATION)
	if err == nil && existing != nil {
		// Windows can propagate a DACL write to all descendants, including
		// every cached runtime. Skip the write only for the exact protected
		// DACL. AI records auto-inheritance history, with the same ACEs.
		current := existing.String()
		if current == "D:P"+entries || current == "D:PAI"+entries {
			return nil
		}
	}
	sd, err := windows.SecurityDescriptorFromString("D:P" + entries)
	if err != nil {
		return err
	}
	acl, _, err := sd.DACL()
	if err != nil {
		return err
	}
	return windows.SetNamedSecurityInfo(path, windows.SE_FILE_OBJECT, windows.DACL_SECURITY_INFORMATION|windows.PROTECTED_DACL_SECURITY_INFORMATION, nil, nil, acl, nil)
}
