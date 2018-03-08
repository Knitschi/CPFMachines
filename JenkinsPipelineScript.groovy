#!groovy

/**
The jenkins pipeline script for a CPF project.

The script expects the job parameters:

params.cpfCIRepository
params.branchOrTag
params.taggingOption
params.packages
params.cpfConfiguration
params.target
params.webserverHost

*/

import static Constants.*
import groovy.json.JsonSlurperClassic


//############################### FUNCTION SECTION ################################
class Constants {
    static final CPF_JENKINSJOB_VERSION = '0.0.0' // how can we get this from a generated file?
    
    // locations
    static final CHECKOUT_FOLDER = 'C O' // this needs a space to test if spaced directories work. It also must be short because of path limits on windows
    static final CPFCMAKE_DIR = 'CPFCMake'

    // stash names
    static final HTML_STASH = "html"

    static final RELEASE_TAGGING_OPTIONS = ['incrementMajor', 'incrementMinor', 'incrementPatch']
    static final TAGGING_OPTIONS = ['internal'] + RELEASE_TAGGING_OPTIONS
}


//############################### SCRIPT SECTION ################################
println( """
####################################################
------------------ Build Parameter -----------------
taggingOption: ${params.taggingOption}
branchOrTag: ${params.branchOrTag}
cpfConfiguration: ${params.cpfConfiguration}
target: ${params.target}
cpfCIRepository: ${params.cpfCIRepository}
webserverHost: ${params.webserverHost}
webserverSSHPort: ${params.webserverSSHPort}
----------------------------------------------------
####################################################
""")

if( params.target == '')
{
    params.target = 'pipeline'
}

def taggingOptionList = params.taggingOption.split(' ')
def taggingOption = ""
def taggedPackage = ""
if( taggingOptionList.size() == 0 || taggingOptionList[0] == '')
{
    echo "No parameter taggingOption given. Use default tagging option \"internal\"."
    taggingOption = 'internal'
}
else
{
    // check that option has an valid value
    taggingOption = taggingOptionList[0]
    if( !TAGGING_OPTIONS.contains(taggingOption) )
    {
        echo "Error! Invalid value  \"${taggingOption}\" for job parameter taggingOption."
        throw new Exception('Invalid build-job parameter.')
    }

    // Get the package option
    if(taggingOptionList.size() == 2)
    {
        taggedPackage = taggingOptionList[1]
    }
}


// For unknown reasons, the repo url can not contain the second : after the machine name
// when used with the GitSCM class. So we remove it here.
parts = params.cpfCIRepository.split(':')
def repository = parts[0] + ':' + parts[1] + parts[2]

//(configurations,commitID) = addRepositoryOperationsStage(repository, params.branchOrTag, taggingOption, taggedPackage)
def retlist = addRepositoryOperationsStage(repository, params.branchOrTag, taggingOption, taggedPackage)
def configurations = retlist[0]
def commitID = retlist[1]
def author = retlist[2]

println(
"""
####################################################
This job is run for commit: ${commitID}
####################################################
""" 
)

addPipelineStage(configurations, repository, commitID, params.target)
// Only tag commits that have been built with the full pipline and all configurations.
if(params.target == 'pipeline' && params.cpfConfiguration == '' )
{
    addTaggingStage(repository, commitID)
}
addUpdateWebPageStage(repository, configurations, commitID)


// Create a temporary branch that contains the the latest revision of the
// main branch (e.g. master) and merge the revisions into it that were pushed to
// the developer branch.
def addRepositoryOperationsStage( repository, branchOrTag, taggingOption, taggedPackage)
{
    def usedConfigurations = []
    def commitID = ""

    stage('Get Build-Configurations')
    {
        node(getDebianNodeLabel())
        {
            ws(getRepositoryName(repository))
            {
                checkoutBranch(repository, branchOrTag)
                dir(CHECKOUT_FOLDER)
                {
                    // Update all owned packages if the commit is at the end of a branch.
                    // Otherwise do nothing
                    sh "cmake -DROOT_DIR=\"\$PWD\" -DGIT_REF=${branchOrTag} -DTAGGING_OPTION=${taggingOption} -DRELEASED_PACKAGE=\"${taggedPackage}\" -P Sources/${CPFCMAKE_DIR}/Scripts/prepareCIRepoForBuild.cmake"

                    // Get the id of HEAD, which will be used in all further steps that do repository check outs.
                    // Using a specific commit instead of a branch makes us invulnerable against changes the may
                    // be pushed to the repo while we run the job.
                    commitID = sh( script:"git rev-parse HEAD", returnStdout: true).trim()
                }

                // read the CiBuiltConfigurations.json file
                usedConfigurations = getBuildConfigurations()
            }
        }
    }

    return [usedConfigurations,commitID]
}

def getDebianNodeLabel()
{
    return "Debian-8.9-${CPF_JENKINSJOB_VERSION}-0"
}

def getBuildConfigurations()
{
    // read the CiBuiltConfigurations.json file
    def fileContent = readFile(file:"${CHECKOUT_FOLDER}/Sources/CIBuildConfigurations/cpfCIBuildConfigurations.json")
    def configurations = new JsonSlurperClassic().parseText(fileContent)
    if(configurations.isEmpty())
    {
        echo "Error! The cpfCIBuildConfigurations.json file does not seem to contain any build configurations."
        throw new Exception('No build configurations defined.')
    }

    def usedConfigurations = []
    if( params.cpfConfiguration != '')
    {
        for(config in configurations)
        {
            if(config.ConfigName == params.cpfConfiguration)
            {
                usedConfigurations.add(config)
            }
        }
        assertConfigurationExists(configurations, params.cpfConfiguration)
    }
    else
    {
        usedConfigurations = configurations
    }

    return usedConfigurations
}

def assertConfigurationExists(configurations, requestedConfig)
{
    def configNames = []
    for(config in configurations)
    {
        configNames.add(config.ConfigName)
    }

    if(!configNames.contains(requestedConfig))
    {
        echo "Error! Requested configuration ${requestedConfig} is not contained in the cpfCIBuildConfigurations.json file."
        def configurationsString = configNames.join(', ')
        echo "Available configurations are ${configurationsString}"
        currentBuild.result = 'FAILURE'

        throw new Exception('Invalid build configuration.')
    }
}

def checkoutBranch(repository, branch)
{
    checkout([$class: 'GitSCM',
            userRemoteConfigs: [[url: repository]],
            branches: [[name: branch]],
            extensions: [
                [$class: 'CleanBeforeCheckout'],
                // We checkout to a subdirectory so the folders for the test files that lie parallel to the repository are still within the workspace.
                [$class: 'RelativeTargetDirectory', 
                    relativeTargetDir: CHECKOUT_FOLDER],
                [$class: 'SubmoduleOption', 
                    disableSubmodules: false, 
                    parentCredentials: false, 
                    recursiveSubmodules: false, 
                    reference: '', 
                    trackingSubmodules: false ]],
            submoduleCfg: []
        ]
    )
}

def addPipelineStage( cpfConfigs, repository, commitId, target)
{
    stage('Build Pipeline')
    {
        def parallelNodes = [:]
        parallelNodes.failFast = true
        
        // add nodes for building the pipeline
        def nodeIndex = 0
        for(config in cpfConfigs)
        {
            echo "Create build node " + config
            def nodeLabel = config.BuildSlaveLabel + '-' + nodeIndex
            echo "Build ${config.ConfigName} under label ${nodeLabel}"
            def myNode = createBuildNode( nodeLabel, config.ConfigName, repository, commitId, target, config?.CompilerConfig)
            parallelNodes[config.ConfigName] = myNode
            nodeIndex++
        }

        // run the nodes
        parallel parallelNodes
    }
}

def createBuildNode( nodeLabel, cpfConfig, repository, commitId, target, compilerConfig)
{
    return {
        node(nodeLabel)
        {
            // get the main name of repository
            ws("${getRepositoryName(repository)}-${cpfConfig}") 
            { 
                checkoutBranch(repository, commitId)

                dir(CHECKOUT_FOLDER)
                {
                    // Make the python scripts available in the root directory
                    // runPythonCommand("Sources/CPFBuildscripts/0_CopyScripts.py")

                    // Setup build configurations
                    // We do not use the ninja build-system for msvc because ninja in combination with mscv can randomly fail with an error thet says that a .pdb file could not be opened.
                    // This usually does not happen when doing a fresh build, but rather when doing incremental builds.
                    // https://github.com/ninja-build/ninja/issues/620
                    runPythonCommand("1_Configure.py ${cpfConfig} --inherits ${cpfConfig}")
                    
                    // generate makefiles
                    runPythonCommand("2_Generate.py ${cpfConfig}")

                    // build the pipeline target
                    def configOption = ''
                    if(compilerConfig) // The build config option is only needed for multi-config generators.
                    {
                        configOption = "--config ${compilerConfig}"
                    }
                    runXvfbWrappedPythonCommand( "3_Make.py ${cpfConfig} --target ${target} ${configOption}" )

                    // stash generated html content
                    dir( "Generated/${cpfConfig}" )
                    {
                        def htmlStash = "${HTML_STASH}${cpfConfig}"
                        stash includes: 'html/**', name: htmlStash
                    }
                    
                    echo "----- The pipeline finished successfully for configuration ${cpfConfig}. -----"
                }
            }
        }
    }
}

def addTaggingStage(repository, commitID)
{
    stage('Tag verified commit')
    {
        node(getDebianNodeLabel())
        {
            ws(getRepositoryName(repository))
            {
                checkoutBranch(repository, commitID)
                dir(CHECKOUT_FOLDER)
                {
                    sh "cmake -DROOT_DIR=\"\$PWD\" -P Sources/${CPFCMAKE_DIR}/Scripts/addVersionTag.cmake"
                }
            }
        }
    }
}

def addUpdateWebPageStage(repository, cpfConfigs, commitID)
{
    stage('Update Project Web-Page')
    {
        node('master')
        {
            def repositoryName = getRepositoryName(repository)
            ws(repositoryName)
            {
                checkoutBranch(repository, commitID) // get the scripts

                def serverHtmlDir = '$PWD/html-on-server'
                def tempHtmlDir = '$PWD/html'
                
                // make sure previous content of the html directory is removed.
                sh "cmake -E remove_directory \"${serverHtmlDir}\""
                sh "mkdir \"${serverHtmlDir}\""
                sh "cmake -E remove_directory \"${tempHtmlDir}\""
                sh "mkdir \"${tempHtmlDir}\""
            
                // collect all produced html content from the build-slaves
                for(cpfConfig in cpfConfigs)
                {
                    unstashFiles(HTML_STASH, cpfConfig.ConfigName)
                }
                // sh "ls -l \"${tempHtmlDir}\""

                def web_host = "root@${params.webserverHost}"
                def port = params.webserverSSHPort
                def projectHtmlDirOnWebserver = "/var/www/html"

                // get the current html content from the web-server
                sh "scp -P ${port} -r ${web_host}:${projectHtmlDirOnWebserver}/* \"${serverHtmlDir}\" || :" // || : suppresses the error message if the server html contains no files

                // merge the new html content into the old html content
                // sh "ls -l \$PWD/${CHECKOUT_FOLDER}/Sources/cmake/Scripts"
                sh "cmake -DSOURCE_DIR=\"${tempHtmlDir}\" -DTARGET_DIR=\"${serverHtmlDir}\" -DROOT_DIR=\"\$PWD/${CHECKOUT_FOLDER}\" -P \"\$PWD/${CHECKOUT_FOLDER}/Sources/${CPFCMAKE_DIR}/Scripts/updateExistingWebPage.cmake\""

                // copy the merge result back to the server
                sh "ssh -p ${port} ${web_host} \"mkdir -p ${projectHtmlDirOnWebserver}\""
                sh "ssh -p ${port} ${web_host} \"rm -rf ${projectHtmlDirOnWebserver}/*\""
                sh "scp -P ${port} -r \"${serverHtmlDir}/*\" ${web_host}:${projectHtmlDirOnWebserver} || :"
                
                echo '----- The project web-page was updated successfully. -----'
            }
        }
    }
}

def getRepositoryName(repository)
{
    def lastPart = repository.split('/').last()
    if(lastPart.matches(~'^.*\\.git$') )
    {
        lastPart = lastPart[0..-5]
    }
    return lastPart
}

def unstashFiles(String stashName, String toolchain)
{
    def fullStashName = stashName + toolchain
    echo "Unstash files from stash: " + fullStashName
    unstash fullStashName
}

def runPythonCommand(command)
{
    def pythonCmd = getPythonCommand()
    runCommand(pythonCmd + ' ' + command)
}

def getPythonCommand()
{
    pythonVersion = sh(returnStdout: true, script: 'python --version').trim()
    def pythonCmd = 'python'
    if(!pythonVersion.matches(~'^.*3\\..*$'))
    {
        pythonCmd = 'python3'
    }
    return pythonCmd
}

def runCommand(command)
{
    if(isUnix())
    {
        return sh(returnStdout: true, script: command).trim()
    }
    else
    {
        return bat(returnStdout: true, script: command).trim()
    }
}

def runXvfbWrappedPythonCommand(command)
{
    if(isUnix())
    {
        // On linux we need the jenkins Xvfb plugin to simulate an x11 server or qt will give us errors that it can not connect to the x11 server.
        wrap([$class: 'Xvfb', parallelBuild: true, displayNameOffset: 1, autoDisplayName: true, assignedLables: 'linux'])
        {
            runPythonCommand(command)
        }
    }
    else
    {
        runPythonCommand(command)
    }
}

def cleanWorkspace(repository, cpfConfig)
{
    echo 'Clean Workspace ...'
    dir("${getRepositoryName(repository)}-${cpfConfig}"){ // todo use 
        deleteDir()
    }
}

def showTree()
{
    if(isUnix())
    {
        sh 'tree'
    }
    else if(os == 'linux')
    {
        bat 'tree /F /A'
    }
}

def devMessage(message)
{
    println '------------------------ ' + message
}