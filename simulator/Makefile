VERSION=$(shell git describe --tags --always)
IMAGE=reboot-subnet-simulator

.PHONY: docker-build
docker-build:
	docker build --no-cache -t $(IMAGE):$(VERSION) .
	docker tag $(IMAGE):$(VERSION) $(IMAGE):latest

.PHONY: docker-push
docker-push:
	docker push $(IMAGE):$(VERSION)

.PHONY: docker-run
docker-run:
	docker run --rm -it --network=host --gpus=all $(IMAGE):$(VERSION) bash
	#docker run --rm -it --network=host $(IMAGE):$(VERSION) bash

.PHONY: docker-push-latest
docker-push-latest:
	docker tag $(IMAGE):$(VERSION) $(IMAGE):latest
	docker push $(IMAGE):latest
