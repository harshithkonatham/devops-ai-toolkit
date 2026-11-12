.PHONY: help install lint test scan check run loadgen image demo release-good release-bad release-slow status clean

UV_RUN  := uv run --locked
IMAGE   := canary-demo:dev
CLUSTER := canary-demo

help: ## Show available commands
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install locked dev dependencies
	uv sync --locked

lint: ## Ruff lint + format check, strict mypy
	$(UV_RUN) ruff check .
	$(UV_RUN) ruff format --check .
	$(UV_RUN) mypy

test: ## Tests with coverage gate
	$(UV_RUN) pytest --cov --cov-fail-under=90

scan: ## Bandit, Checkov, ShellCheck
	$(UV_RUN) bandit -q -r src -ll
	uvx checkov@3.3.29 --compact --quiet --framework dockerfile -f Dockerfile
	uvx checkov@3.3.29 --compact --quiet --framework kubernetes -d deploy/k8s
	cd scripts && uvx --from shellcheck-py shellcheck -x ./*.sh

check: lint test scan ## Everything CI runs before building the image

run: ## Run the app locally on :8000 (try ERROR_RATE=0.5 make run)
	PYTHONPATH=src VERSION=$${VERSION:-local} python3 -m canary_demo

loadgen: ## Send traffic to the local app
	PYTHONPATH=src python3 -m canary_demo.loadgen run --url http://localhost:8000/ --rps 10

image: ## Build the container image
	docker build -t $(IMAGE) .

demo: ## Full demo on a local kind cluster (needs docker, kind, kubectl)
	CLUSTER=$(CLUSTER) scripts/demo.sh

release-good: ## Ship a healthy release to the demo cluster (VERSION=v5)
	scripts/release.sh $${VERSION:-v5}

release-bad: ## Ship a release with 50% errors; expect rollback (VERSION=v6)
	EXPECT=Degraded scripts/release.sh $${VERSION:-v6} 0.5

release-slow: ## Ship a release with +400 ms latency; expect rollback (VERSION=v7)
	EXPECT=Degraded scripts/release.sh $${VERSION:-v7} 0 400

status: ## Show the rollout, analysis runs and pods
	kubectl -n canary-demo get rollout,analysisrun,replicaset,pods

clean: ## Delete the demo kind cluster
	kind delete cluster --name $(CLUSTER)
