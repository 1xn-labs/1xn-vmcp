.PHONY: help install dev build test clean docker docs run-tests start-docker

# Colors
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

help: ## Show this help message
	@echo "$(CYAN)vMCP - Virtual Model Context Protocol$(RESET)"
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2}'

run: ## Run the vMCP application (usage: make run LOG_LEVEL=debug)
	@echo "$(CYAN)Starting vMCP application...$(RESET)"
	@if [ -n "$(LOG_LEVEL)" ]; then \
		echo "$(YELLOW)Using log level: $(LOG_LEVEL)$(RESET)"; \
		cd backend && uv run python -m vmcp.cli.main run --log-level $(LOG_LEVEL); \
	else \
		cd backend && uv run python -m vmcp.cli.main run; \
	fi

test-servers: ## Start both test servers
	@echo "$(CYAN)Killing processes on ports 8001 and 8002...$(RESET)"
	@lsof -ti:8001 | xargs kill -9 2>/dev/null || true
	@lsof -ti:8002 | xargs kill -9 2>/dev/null || true
	@echo "$(GREEN)Ports cleared!$(RESET)"
	@echo "$(CYAN)Starting both test servers...$(RESET)"
	@cd backend && (uv run python tests/test_server/test_http_server.py & uv run python tests/mcp_server/start_mcp_servers.py & wait)

build-frontend: ## Build frontend
	@echo "$(CYAN)Building frontend...$(RESET)"
	cd frontend && npm install && VITE_VMCP_OSS_BUILD=true VITE_BACKEND_URL=http://localhost:8000/api npm run build
	@echo "$(CYAN)Copying frontend to backend package...$(RESET)"
	rm -rf backend/public/frontend
	mkdir -p backend/public
	cp -r frontend/dist backend/public/frontend
	@echo "$(GREEN)Frontend built and copied to backend/public/frontend!$(RESET)"

run-tests: ## Run tests (usage: make run-tests ARGS="-v" or make run-tests ARGS="tests/test_file.py")
	@echo "$(CYAN)Running tests...$(RESET)"
	cd backend && uv run pytest $(ARGS)

start-docker: ## Build frontend and start Docker services
	@echo "$(CYAN)Building frontend for Docker...$(RESET)"
	@$(MAKE) build-frontend
	@echo ""
	@echo "$(CYAN)Starting Docker services...$(RESET)"
	@cd docker && docker-compose up --build --force-recreate
	@echo "$(GREEN)Docker services started!$(RESET)"
	@echo "$(YELLOW)Access the application at: http://localhost:8000$(RESET)"
