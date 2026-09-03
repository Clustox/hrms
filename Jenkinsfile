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
                // the Quality Gate stage below waits on.
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