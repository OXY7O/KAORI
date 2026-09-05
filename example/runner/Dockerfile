FROM ubuntu:24.04

ARG RUNNER_VERSION=2.337.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl docker.io git jq libicu74 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1001 --shell /bin/bash runner \
    && mkdir -p /runner \
    && chown runner:runner /runner

WORKDIR /runner
RUN curl --fail --location --silent --show-error \
      "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
      --output /tmp/runner.tar.gz \
    && tar -xzf /tmp/runner.tar.gz -C /runner \
    && rm /tmp/runner.tar.gz \
    && ./bin/installdependencies.sh \
    && chown -R runner:runner /runner

COPY --chown=runner:runner entrypoint.sh /usr/local/bin/kaori-demo-runner
RUN chmod 0755 /usr/local/bin/kaori-demo-runner

USER runner
ENTRYPOINT ["kaori-demo-runner"]
