package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestInstallShDetectRcFile_UsesLoginShell(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("install.sh is not used on Windows")
	}
	bashPath, err := exec.LookPath("bash")
	if err != nil {
		t.Skip("bash not found")
	}

	scriptPath := filepath.Join("..", "install.sh")

	cases := []struct {
		name        string
		shell       string
		createFiles []string
		wantFile    string
	}{
		{name: "zsh", shell: "/usr/bin/zsh", wantFile: ".zshrc"},
		{name: "zsh_no_path", shell: "zsh", wantFile: ".zshrc"},
		{name: "zsh_with_args", shell: "/usr/bin/zsh -l", wantFile: ".zshrc"},
		{name: "zsh_dash_prefix", shell: "-zsh", wantFile: ".zshrc"},
		{name: "bash", shell: "/bin/bash", wantFile: ".bashrc"},
		{name: "bash_no_path", shell: "bash", wantFile: ".bashrc"},
		{name: "bash_with_args", shell: "/bin/bash -l", wantFile: ".bashrc"},
		{name: "bash_dash_prefix", shell: "-bash", wantFile: ".bashrc"},
		{name: "unknown", shell: "/usr/bin/fish", wantFile: ".bashrc"},
		{name: "zprofile_exists_but_use_zshrc", shell: "/usr/bin/zsh", createFiles: []string{".zprofile"}, wantFile: ".zshrc"},
		{name: "bash_profile_exists_but_use_bashrc", shell: "/bin/bash", createFiles: []string{".bash_profile"}, wantFile: ".bashrc"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			tmpHome := t.TempDir()
			for _, name := range tc.createFiles {
				if err := os.WriteFile(filepath.Join(tmpHome, name), []byte("# test\n"), 0o600); err != nil {
					t.Fatalf("creating %s: %v", name, err)
				}
			}

			cmd := exec.Command(bashPath, scriptPath, "--print-rc-file")
			cmd.Env = append(
				os.Environ(),
				"HOME="+tmpHome,
				"SHELL="+tc.shell,
			)
			out, err := cmd.Output()
			if err != nil {
				t.Fatalf("running install.sh: %v", err)
			}
			got := strings.TrimSpace(string(out))
			want := filepath.Join(tmpHome, tc.wantFile)
			if got != want {
				t.Fatalf("RC file mismatch: got %q want %q", got, want)
			}
		})
	}
}
