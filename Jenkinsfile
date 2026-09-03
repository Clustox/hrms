pipeline {
    agent any
    options { timeout(time: 30, unit: 'MINUTES') }
    environment {
        COMPOSE_FILE = '/opt/app/hrms/docker/docker-compose.yml'
        PROJECT = 'docker'
    }
    stages {
        stage('Checkout') {
            steps { checkout scm }
        }
        stage('SonarQube Analysis') {
            steps {
                // The agent has Docker but no sonar-scanner CLI and no SonarQube Scanner
                // tool installation, so the official scanner image is used. withSonarQubeEnv
                // injects SONAR_HOST_URL / SONAR_AUTH_TOKEN and records the report task that
                // the Quality Gate stage below waits on. sonar.working.directory is
                // overridden because the image's baked-in /tmp/.scannerwork is owned by
                // uid 1000 and unwritable under -u; putting it in the mounted workspace
                // also lands report-task.txt where waitForQualityGate looks for it.
                withSonarQubeEnv('MySonarQube') {
                    sh '''
                      docker run --rm \
                        -u "$(id -u):$(id -g)" \
                        -e SONAR_HOST_URL="$SONAR_HOST_URL" \
                        -e SONAR_TOKEN="$SONAR_AUTH_TOKEN" \
                        -e SONAR_USER_HOME=/tmp/.sonar \
                        -v "$WORKSPACE:/usr/src" \
                        -w /usr/src \
                        sonarsource/sonar-scanner-cli:latest \
                        -Dsonar.working.directory=/usr/src/.scannerwork \
                        -Dsonar.projectVersion="${GIT_COMMIT:-$BUILD_NUMBER}"
                    '''
                }
            }
        }
        stage('Quality Gate') {
            steps {
                // Bounded wait: without a SonarQube webhook back to Jenkins this would
                // otherwise block until the job-level 30 minute timeout.
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }
        stage('Fetch Sonar Issues') {
            steps {
                // Read-only reporting. Wrapped in catchError so that a SonarQube outage or
                // an expired token marks the build UNSTABLE instead of blocking the deploy
                // stages that follow. The token goes in an Authorization header, never in
                // the query string, so it cannot leak into proxy or access logs.
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    withCredentials([string(credentialsId: 'sonarqube-readonly-token', variable: 'SONAR_RO_TOKEN')]) {
                        sh '''
                          set -eu
                          PS=500
                          TMP=$(mktemp -d)
                          trap 'rm -rf "$TMP"' EXIT
                          page=1
                          while : ; do
                            curl --fail --silent --show-error \
                              -H "Authorization: Bearer $SONAR_RO_TOKEN" \
                              -o "$TMP/page-$page.json" \
                              "https://sonar.theclustox.com/api/issues/search?componentKeys=hrms&resolved=false&ps=$PS&p=$page"
                            total=$(jq -r '.paging.total' "$TMP/page-$page.json")
                            fetched=$(( page * PS ))
                            echo "fetched page $page (up to $fetched of $total open issues)"
                            [ "$fetched" -ge "$total" ] && break
                            # api/issues/search refuses p*ps beyond 10000
                            [ "$fetched" -ge 10000 ] && { echo "WARNING: capped at 10000 issues"; break; }
                            page=$(( page + 1 ))
                          done
                          # The warnings-ng SonarQube parser sniffs the response format from the
                          # top-level keys, so the merged document has to look like one big
                          # api/issues/search page -- dropping total/p/ps makes it silently
                          # parse to zero issues.
                          jq -s '
                            (map(.issues) | add)   as $iss |
                            (.[0].paging.total)    as $tot |
                            {
                              total:       $tot,
                              p:           1,
                              ps:          ($iss | length),
                              paging:      {pageIndex: 1, pageSize: ($iss | length), total: $tot},
                              effortTotal: (map(.effortTotal // 0) | add),
                              issues:      $iss,
                              components:  (map(.components // []) | add | unique_by(.key))
                            }' "$TMP"/page-*.json > sonar-issues.json
                          echo "merged $(jq '.issues | length' sonar-issues.json) issues into sonar-issues.json"
                        '''
                    }
                }
            }
        }
        stage('Publish Issue Report') {
            steps {
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    recordIssues(tools: [sonarQube(pattern: 'sonar-issues.json')])
                }
            }
        }
        stage('Redeploy dev stack') {
            steps {
                sh 'docker compose -f $COMPOSE_FILE -p $PROJECT down'
                sh 'docker compose -f $COMPOSE_FILE -p $PROJECT up -d --build'
            }
        }
        stage('Health check') {
            steps {
                sh '''
                  for i in $(seq 1 80); do
                    if curl -sf http://localhost:8000 > /dev/null; then
                      echo "hrms is up"; exit 0
                    fi
                    sleep 15
                  done
                  echo "hrms did not become healthy in time"; exit 1
                '''
            }
        }
    }
}