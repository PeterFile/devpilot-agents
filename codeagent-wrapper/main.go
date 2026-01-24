package main

import "codeagent-wrapper/internal/wrapper"

var version string

func main() {
	if version != "" {
		wrapper.SetVersion(version)
	}
	wrapper.Main()
}
