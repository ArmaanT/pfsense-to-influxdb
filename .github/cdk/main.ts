import dedent from 'ts-dedent';
import { Construct } from "constructs";
import { App, CheckoutJob, Stack, Workflow } from "cdkactions";

export class PfSenseToInfluxDBStack extends Stack {
  constructor(scope: Construct, name: string) {
    super(scope, name);

    const workflows = new Workflow(this, 'build-and-publish', {
      name: 'Build and Publish',
      on: {
        pullRequest: {},
        push: {
          branches: ['**'],
          tags: ['[0-9]+.[0-9]+.[0-9]+'],
        },
      }
    });

    const formatImageName = (tag: string): string => `armaant/pfsense-to-influxdb:${tag}`

    new CheckoutJob(workflows, 'build-and-publish', {
      runsOn: 'ubuntu-latest',
      steps: [
        {
          id: 'tag',
          name: 'Get tag version',
          run: dedent`
          RAW_TAG=\${GITHUB_REF#refs/*/}
          # Strip / characters
          TAG=\${RAW_TAG/\\//-}
          echo ::set-output name=tag::\${TAG}`,
        },
        {
          uses: 'docker/setup-qemu-action@v1',
        },
        {
          uses: 'docker/setup-buildx-action@v1',
        },
        {
          uses: 'docker/login-action@v1',
          with: {
            username: '${{ secrets.DOCKER_USERNAME }}',
            password: '${{ secrets.DOCKER_PASSWORD }}',
          },
        },
        {
          name: 'Build/Publish',
          uses: 'docker/build-push-action@v2',
          with: {
            push: "${{ startsWith(github.ref, 'refs/tags') }}",
            tags: ["latest", "${{ steps.tag.outputs.tag }}"].map(formatImageName).join()
          },
        },
      ]
    });
  }
}

const app = new App();
new PfSenseToInfluxDBStack(app, 'cdk');
app.synth();
