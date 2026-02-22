# Minikube performance testing

Compare network performance of minikube drivers (krunkit, vfkit) using
iperf3 benchmarks across different network configurations.

## Test dimensions

- **Drivers**: krunkit, vfkit
- **Networks**: host (direct VM IP), pod (Kubernetes NodePort service)
- **Where**: host (iperf3 on macOS), vm (iperf3 inside client VM via kubectl exec)
- **Tests**: tx, rx, bidir

## Running tests

Run all tests with default settings (60 seconds per test):

    % cd test/minikube
    % ./test.py run

Use a local minikube build:

    % ./test.py run --minikube ~/src/minikube/out/minikube

Quick test with shorter duration:

    % ./test.py run -t 10

Test only specific combinations:

    % ./test.py run -d krunkit -n host --tests tx rx

Results are written to `out/bench/` as iperf3 JSON files and logs to
`out/test.log`.

## Analyzing results

Generate plots and a markdown report from the test results:

    % ./test.py analyze

This creates line plots in `out/plots/` and a report at `out/report.md`.

## Test setup

The test creates two minikube clusters ("server" and "client") for each
driver, deploys iperf3 using kustomize overlays from the `iperf3/`
directory, runs all test combinations, then deletes the clusters.

For host network tests, iperf3 connects directly to the server VM's IP
on port 5201. For pod network tests, it connects through a Kubernetes
NodePort service on port 30201.
