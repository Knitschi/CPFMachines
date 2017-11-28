 #!/usr/bin/env python3

 # This script removes and adds and starts all docker container of the CppCodeBase project infrastructure.
 # Curently the containers are:
 # jenkins-master
 # jenkins-slave-linux-0
 # ccb-web-server

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"




# Removes a running docker container
# Arg1: The name of the container
removeContainer()
{
    RUNNING_CONTAINER="$(docker ps)"
    if [[ $RUNNING_CONTAINER == *"$1"* ]]; then
        docker stop $1
    fi
    
    ALL_CONTAINER="$(docker ps -a)"
    if [[ $ALL_CONTAINER == *"$1"* ]]; then
        docker rm -f $1
    fi
}

clearDocker()
{
    removeContainer $DOCUMENTS_SERVER_CONTAINER
    removeContainer $JENKINS_MASTER_CONTAINER
    removeContainer $FULL_LINUX_SLAVE_CONTAINER_NAME
    
    DOCKER_NETWORKS="$(docker network ls)"
    if [[ $DOCKER_NETWORKS == *"$NETWORK_NAME"* ]]; then
        docker network rm $NETWORK_NAME
    fi
    
}

clearHostShareDirectories()
{
    clearDirectory $JENKINS_WORKSPACE_HOST
    
    # Create the directory for the html share on the host if it does not exist
    # We do not clear this directory because it contains persistent data like results
    # of previous builds.
    if [ ! -e "$HTML_SHARE_HOST" ]; then
        mkdir -p $HTML_SHARE_HOST
    fi
}

# This functions deletes the given directory and all its content and recreates it.
# Arg1: The path to the directory
clearDirectory()
{
    echo "Cleaning directory $1"
    rm -rf $1
    mkdir -p $1
}

createDockerNetwork()
{
    # create the network
    docker network create --subnet=172.19.0.0/16 $NETWORK_NAME
}

createJenkinsConfigFiles()
{
    rm -rf JenkinsConfig/nodes
    mkdir -p JenkinsConfig/nodes
    
    bash $SCRIPT_DIR/createLinuxNodeConfigFile.sh $FULL_LINUX_SLAVE_CONTAINER_NAME $JENKINS_LINUX_SLAVE_IP
    bash $SCRIPT_DIR/createWindowsNodeConfigFile.sh $FULL_WINDOWS_SLAVE_CONTAINER_NAME
}

buildAndStartJenkinsMaster() 
{
    echo "----- Build and start the docker MASTER container $JENKINS_MASTER_CONTAINER"

    docker build -t $JENKINS_MASTER_CONTAINER-image -f $SCRIPT_DIR/DockerfileJenkinsMaster $SCRIPT_DIR

    # --env JAVA_OPTS="-Djenkins.install.runSetupWizard=false" is supposed to prevent the plugin install wizard on the first startup.
    # The jenkins master and its slaves comunicate over the bridge network. 
    # This means the master and the slaves must be on the same host. This should later be upgraded to a swarm.
    docker run \
        --detach \
        --volume $JENKINS_WORKSPACE_HOST:$JENKINS_WORKSPACE_JENKINS_MASTER \
        --env JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
        --publish 8080:8080 \
        --publish 50000:50000 \
        --net $NETWORK_NAME \
        --ip $JENKINS_MASTER_IP \
        --name $JENKINS_MASTER_CONTAINER \
        $JENKINS_MASTER_CONTAINER-image

    # add global gitconfig after mounting the workspace volume, otherwise is gets deleted. 
    docker exec $JENKINS_MASTER_CONTAINER git config --global user.email not@valid.org
    docker exec $JENKINS_MASTER_CONTAINER git config --global user.name jenkins
  
}

buildAndStartDocumentationServer()
{
    # The document server must be started before the jenkins slave is started because mounting the shared volume here sets the
    # owner of the share to root an only the jenkins container can set it to jenkins.
    
    # We set the --restart option for this container because it does not restart automatically like the others.
    # It would be cleaner to have a systemd script on the host for stopping and starting the containers.
    
    echo "----- Build and start the documents web-server container $CONTAINER_NAME"

    docker build -t $DOCUMENTS_SERVER_CONTAINER-image -f $SCRIPT_DIR/DockerfileCcbWebServer $SCRIPT_DIR
    docker run \
        --detach \
        --publish 80:80 \
        --volume $HTML_SHARE_HOST:$HTML_SHARE_WEB_SERVER \
        --name $DOCUMENTS_SERVER_CONTAINER \
        --net $NETWORK_NAME \
        --ip $DOCUMENTS_SERVER_IP \
        $DOCUMENTS_SERVER_CONTAINER-image

    # copy the doxyserach.cgi to the html share
    docker exec --user root:root $DOCUMENTS_SERVER_CONTAINER rm -fr $HTML_SHARE_WEB_SERVER/cgi-bin
    docker exec --user root:root $DOCUMENTS_SERVER_CONTAINER mkdir $HTML_SHARE_WEB_SERVER/cgi-bin
    docker exec --user root:root $DOCUMENTS_SERVER_CONTAINER mkdir $HTML_SHARE_WEB_SERVER/cgi-bin/doxysearch.db
    docker exec --user root:root $DOCUMENTS_SERVER_CONTAINER cp -r -f /usr/local/bin/doxysearch.cgi $HTML_SHARE_WEB_SERVER/cgi-bin

    # set cgi-bin ownership on the host
    #sudo chown -R $USER:$USER $JENKINS_WORKSPACE_HOST/html
    # set cgi-bin ownership on the jenkins master
    #docker exec --user root:root $JENKINS_MASTER_CONTAINER chown -R jenkins:jenkins $HTML_SHARE_JENKINS_MASTER
}

buildAndStartJenkinsLinuxSlave()
{
    # Start the container.
    echo "----- Build and start the docker SLAVE container $CONTAINER_NAME"

    docker build -t $LINUX_SLAVE_BASE_NAME-image -f $SCRIPT_DIR/DockerfileJenkinsSlaveLinux $SCRIPT_DIR
    docker run \
        --net $NETWORK_NAME \
        --ip $JENKINS_LINUX_SLAVE_IP \
        --name $FULL_LINUX_SLAVE_CONTAINER_NAME \
        --detach $LINUX_SLAVE_BASE_NAME-image
}

# ARG1 container-name 
# ARG2 container-home-directory
createRSAKeyFilePairOnContainer()
{
    echo "----- Enable ssh key file connection between $1 and datenbunker"
    echo "... copy script $CREATE_KEY_PAIR_SCRIPT to container"
    docker cp $SCRIPT_DIR/$CREATE_KEY_PAIR_SCRIPT $1:$2/$CREATE_KEY_PAIR_SCRIPT

    echo "... copy script $ADD_KNOWN_HOST_SCRIPT to container"
    docker cp $SCRIPT_DIR/$ADD_KNOWN_HOST_SCRIPT $1:$2/$ADD_KNOWN_HOST_SCRIPT

    echo "... execute script $CREATE_KEY_PAIR_SCRIPT in container"
    # This will create the key-pair on the container. We need to do this in the container or ssh will not accept the private key file.
    docker exec --user jenkins:jenkins $1 /bin/bash $2/$CREATE_KEY_PAIR_SCRIPT $1
}

# ARG1 container-name
# ARG2 container-home-directory
grantContainerSSHAccessToDatenbunker()
{
    # COPY AND REGISTER THE PUBLIC KEY WITH DATENBUNKER
    # The connection is used to access the git repository
    # This requires access to the datenbunker.
    PUBLIC_KEY_FILE=$1$PUBLIC_KEY_FILE_POSTFIX
    GIT_SERVER_PUBLIC_KEY_DIR=/etc/config/ssh
    TEMP_DIR_HOST=~/temp
    mkdir -p $TEMP_DIR_HOST
    rm -f $TEMP_DIR_HOST/$PUBLIC_KEY_FILE # delete previously copied key-files
    
    # Copy the public key from the jenkins jome directory to the jenkins-workspace directory on the host
    docker cp $1:$2/$PUBLIC_KEY_FILE $TEMP_DIR_HOST
    # Then copy it to the repository machine
    scp $TEMP_DIR_HOST/$PUBLIC_KEY_FILE admin@datenbunker.local:$GIT_SERVER_PUBLIC_KEY_DIR

    # Remove previously appended public keys from the given container and append the new public key to the authorized_keys file.
    # - print file without lines containing machine name string, then append new key to end of file
    AUTHORIZED_KEYS_FILE=$GIT_SERVER_PUBLIC_KEY_DIR/authorized_keys
    ssh admin@datenbunker \
    "cat $AUTHORIZED_KEYS_FILE | grep -v $1 >> $GIT_SERVER_PUBLIC_KEY_DIR/keys_temp &&\
    mv -f $GIT_SERVER_PUBLIC_KEY_DIR/keys_temp $AUTHORIZED_KEYS_FILE &&\
    cat $GIT_SERVER_PUBLIC_KEY_DIR/$PUBLIC_KEY_FILE >> $AUTHORIZED_KEYS_FILE" 
    
    # Add datenbunker as known host to prevent the authentication request on the first connect
    docker exec --user jenkins:jenkins $1 /bin/bash $2/$ADD_KNOWN_HOST_SCRIPT $DATENBUNKER
}

grantJenkinsMasterSSHAccessToJenkinsLinuxSlave()
{
    echo "----- Grant $JENKINS_MASTER_CONTAINER ssh access to $FULL_LINUX_SLAVE_CONTAINER_NAME"
    PUBLIC_KEY_FILE=$JENKINS_MASTER_CONTAINER$PUBLIC_KEY_FILE_POSTFIX
    
    # COPY AND REGISTER THE PUBLIC KEY WITH THE SLAVE 
    # Jenkins handles linux slaves with an ssh connection.
    docker cp $JENKINS_WORKSPACE_HOST/$PUBLIC_KEY_FILE $FULL_LINUX_SLAVE_CONTAINER_NAME:$JENKINS_HOME_JENKINS_SLAVE/.ssh/authorized_keys
    # Add slave as known host to prevent the authentication request on the first connect
    docker exec --user jenkins:jenkins $JENKINS_MASTER_CONTAINER /bin/bash $JENKINS_WORKSPACE_JENKINS_MASTER/$ADD_KNOWN_HOST_SCRIPT $JENKINS_LINUX_SLAVE_IP
}

grantJenkinsMasterSSHAccessToJenkinsWindowsSlave()
{
    echo "----- Grant $JENKINS_MASTER_CONTAINER ssh access to $JENKINS_SLAVE_WINDOWS"

    # copy the public key file from the jenkins master to build slave
    SSH_DIR=C:/Users/$JENKINS_SLAVE_WINDOWS_USER/.ssh
    scp $JENKINS_WORKSPACE_HOST/$PUBLIC_KEY_FILE $JENKINS_SLAVE_WINDOWS_USER@$JENKINS_SLAVE_WINDOWS:$SSH_DIR
    
    # Add the public key to the Bitvise SSH Server that is running on the windows slave
    # 1. Update the authorized_keys file by removing the old key and adding the new one.
    # 2. With the Bitvise SSH Server the keys in the authorized_keys file are only imported to the server when the windows user logs out. 
    # To force an immediate update, we use the Bitvise SSH Client tool spksc to register the public key with the server.
    # The synchronisation mechanism with the authorized_keys file will make sure that public keys from previous runs 
    # of this script are automatically removed from the servers public key list. This step requires to enter the password again.
    # 
    ssh $JENKINS_SLAVE_WINDOWS_USER@$JENKINS_SLAVE_WINDOWS <<DATA
cd $SSH_DIR
type authorized_keys
type authorized_keys | findstr /v $JENKINS_MASTER_CONTAINER >> keys_temp
type keys_temp
move /y keys_temp authorized_keys
type $PUBLIC_KEY_FILE >> authorized_keys
cd "C:/Program Files (x86)/Bitvise SSH Client"
spksc knitschi@buildknechtwin -pw=3utterBro+ -unat=n -cmd="Add File $SSH_DIR/$PUBLIC_KEY_FILE"
DATA
    
    # Add the salve to the known hosts
    docker exec --user jenkins:jenkins $JENKINS_MASTER_CONTAINER /bin/bash $JENKINS_WORKSPACE_JENKINS_MASTER/$ADD_KNOWN_HOST_SCRIPT $JENKINS_SLAVE_WINDOWS
}

grantJenkinsMasterSSHAccessToWebServer()
{
    AUTHORIZED_KEYS_FILE=/root/.ssh/authorized_keys
    PUBLIC_KEY_FILE=$JENKINS_MASTER_CONTAINER$PUBLIC_KEY_FILE_POSTFIX

    docker cp $JENKINS_WORKSPACE_HOST/$PUBLIC_KEY_FILE $DOCUMENTS_SERVER_CONTAINER:$AUTHORIZED_KEYS_FILE
    docker exec $DOCUMENTS_SERVER_CONTAINER chown root:root $AUTHORIZED_KEYS_FILE
    docker exec $DOCUMENTS_SERVER_CONTAINER chmod 600 $AUTHORIZED_KEYS_FILE
    docker exec $DOCUMENTS_SERVER_CONTAINER service ssh start
    
    # Add doc-server as known host to prevent the authentication request on the first connect
    docker exec --user jenkins:jenkins $JENKINS_MASTER_CONTAINER /bin/bash $JENKINS_WORKSPACE_JENKINS_MASTER/$ADD_KNOWN_HOST_SCRIPT $DOCUMENTS_SERVER_IP
}

configureJenkinsMaster()
{
    # ------ COPY JENKINS CONFIGURATION TO MASTER --------
    echo "---- Copy jenkins config.xml files to jenkins master."
    
    cp -rf $SCRIPT_DIR/JenkinsConfig/* $JENKINS_WORKSPACE_HOST
    
    # restart jenkins to make sure the config.xml files get loaded.
    docker stop $JENKINS_MASTER_CONTAINER
    docker start $JENKINS_MASTER_CONTAINER
}

####################################################################################

# ---------------------------- START JENKINS MASTER ---------------------------------

# Exit script on error
set -e
# Print commands in raw and replaced form
set -x


# Directories and Variables
# In the future there may be multiple slaves so the script provides the LINUX_SLAVE_INDEX to destinguish between them.
LINUX_SLAVE_INDEX=0
WINDOWS_SLAVE_INDEX=0
#CPP_CODE_BASE_JOB_NAME=CppCodeBase

# docker entities names
# container
DOCUMENTS_SERVER_CONTAINER=ccb-web-server
JENKINS_MASTER_CONTAINER=jenkins-master
LINUX_SLAVE_BASE_NAME=jenkins-slave-linux
FULL_LINUX_SLAVE_CONTAINER_NAME=$LINUX_SLAVE_BASE_NAME-$LINUX_SLAVE_INDEX
FULL_WINDOWS_SLAVE_CONTAINER_NAME=jenkins-slave-windows-$WINDOWS_SLAVE_INDEX
# networks
NETWORK_NAME=CppCodeBaseNetwork

# container ips
DOCUMENTS_SERVER_IP='172.19.0.2'
JENKINS_MASTER_IP='172.19.0.3'
JENKINS_LINUX_SLAVE_IP='172.19.0.4'

# other machines and users
DATENBUNKER=datenbunker
DATENBUNKER_IP="$(dig +short $DATENBUNKER.fritz.box)" # This will get the current ip address of the datenbunker machine.
JENKINS_SLAVE_WINDOWS=buildknechtwin
JENKINS_SLAVE_WINDOWS_USER=Knitschi