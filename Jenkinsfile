pipeline {
  agent any
  environment {
    IMAGE = "syedshahul/tirupati-auto-app"
  }
  stages {
    stage('Checkout') {
      steps { checkout scm }
    }
    stage('Build') {
      steps {
        // Changed 'sh' to 'bat' and used Windows environment variable syntax (%VAR%)
        bat 'docker build -t %IMAGE%:%BUILD_NUMBER% -t %IMAGE%:latest .'
      }
    }
    stage('Push') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub',
            usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          // Changed 'sh' to 'bat'
          bat '''
            echo %DH_PASS% | docker login -u "%DH_USER%" --password-stdin
            docker push %IMAGE%:%BUILD_NUMBER%
            docker push %IMAGE%:latest
          '''
        }
      }
    }
  }
  post {
    always { 
      // Changed 'sh' to 'bat'
      bat 'docker logout || true' 
    }
  }
}
