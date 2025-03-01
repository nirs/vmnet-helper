//go:build darwin

// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

package vmnet_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/nirs/vmnet-helper/go/vmnet"
)

func TestHelperAvailable(t *testing.T) {
	if !vmnet.HelperAvailable() {
		t.Fatal("vmnet-helper is not installed")
	}
}

func TestSocket(t *testing.T) {
	log := filepath.Join(t.TempDir(), "helper.log")
	logfile, err := os.Create(log)
	if err != nil {
		t.Fatal(err)
	}
	defer logfile.Close()

	// vmnet returns UPPERCASE uuid.
	interfaceID := strings.ToUpper(vmnet.UUIDFromName(t.Name()))

	helper := vmnet.NewHelper(vmnet.HelperOptions{
		Socket:      "vmnet-helper.sock",
		Logfile:     logfile,
		InterfaceID: interfaceID,
		Verbose:     true,
	})

	t.Log("Starting helper with socket")
	if err := helper.Start(); err != nil {
		t.Fatal(err)
	}
	defer helper.Stop()

	info := helper.InterfaceInfo()
	if info == nil {
		t.Fatalf("nil interface info")
	} else {
		buf, err := json.MarshalIndent(info, "", "  ")
		if err != nil {
			t.Fatal(err)
		}
		t.Logf("helper interface:\n%s", buf)
		if info.InterfaceID != interfaceID {
			t.Fatalf("expected interface id %q, got %q", interfaceID, info.InterfaceID)
		}
	}

	t.Log("Stopping helper")
	if err := helper.Stop(); err != nil {
		t.Fatal(err)
	}
	buf, err := os.ReadFile(log)
	if err != nil {
		t.Fatal(err)
	}
	t.Logf("helper log:\n%s", buf)
}

func TestFd(t *testing.T) {
	log := filepath.Join(t.TempDir(), "helper.log")
	logfile, err := os.Create(log)
	if err != nil {
		t.Fatal(err)
	}
	defer logfile.Close()

	fd1, fd2, err := vmnet.Socketpair()
	if err != nil {
		t.Fatal(err)
	}
	defer fd1.Close()
	defer fd2.Close()

	// vmnet returns UPPERCASE uuid.
	interfaceID := strings.ToUpper(vmnet.UUIDFromName(t.Name()))

	helper := vmnet.NewHelper(vmnet.HelperOptions{
		Fd:          fd1,
		Logfile:     logfile,
		InterfaceID: interfaceID,
		Verbose:     true,
	})

	t.Logf("Starting helper with fd %v", fd1.Fd())
	if err := helper.Start(); err != nil {
		t.Fatal(err)
	}
	defer helper.Stop()

	info := helper.InterfaceInfo()
	if info == nil {
		t.Fatalf("nil interface info")
	} else {
		buf, err := json.MarshalIndent(info, "", "  ")
		if err != nil {
			t.Fatal(err)
		}
		t.Logf("helper interface:\n%s", buf)
		if info.InterfaceID != interfaceID {
			t.Fatalf("expected interface id %q, got %q", interfaceID, info.InterfaceID)
		}
	}

	t.Log("Stopping helper")
	if err := helper.Stop(); err != nil {
		t.Fatal(err)
	}
	buf, err := os.ReadFile(log)
	if err != nil {
		t.Fatal(err)
	}
	t.Logf("helper log:\n%s", buf)
}

func TestUUIDFromName(t *testing.T) {
	cases := []struct {
		Name string
		UUID string
	}{
		{"", "e3b0c442-98fc-4c14-9afb-f4c8996fb924"},
		{"vm1", "7b11e3d1-b4ef-47af-be81-aa2aba7af47f"},
		{"vm2", "36d01e0c-cdf7-42eb-b5ea-55c6d0d47155"},
		{"vm235.vms.example.com", "8d72c924-06bb-4504-ac9b-e4c6daa92c3d"},
	}
	for _, c := range cases {
		actual := vmnet.UUIDFromName(c.Name)
		if actual != c.UUID {
			t.Fatalf("expected uuid %q for name %q, got %q", c.UUID, c.Name, actual)
		}
	}
}
