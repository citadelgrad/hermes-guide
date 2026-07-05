.PHONY: up down logs status restart deploy env provision seed

# Generate .env for Docker Compose from .envrc (strips 'export' prefixes).
# Docker Compose env_file expects KEY=VALUE; .envrc uses 'export KEY=VALUE'.
env:
	@[ -f .envrc ] || (echo "Error: .envrc not found. Copy backend/.envrc.example to .envrc and fill in values." && exit 1)
	@sed 's/^export //' .envrc > .env
	@echo ".env generated from .envrc"

up:
	@[ -f .env ] || $(MAKE) env
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

status:
	docker compose ps

restart:
	docker compose restart

provision:
	scripts/provision.sh dfw

seed:
	scripts/seed.sh

deploy:
	cd backend && fly deploy
