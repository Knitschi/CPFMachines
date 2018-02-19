#!groovy

/**
The jenkins pipeline script for a CPF project.

The script expects the job parameters:

params.buildRepository
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
    static final CHECKOUT_FOLDER = 'Check out dir'
    static final CPFCMAKE_DIR = 'CPFCMake'

    // stash names
    static final HTML_STASH = "html"

    static final RELEASE_TAGGING_OPTIONS = ['incrementMajor', 'incrementMinor', 'incrementPatch']
    static final TAGGING_OPTIONS = [ 'noTagging', 'internal'] + RELEASE_TAGGING_OPTIONS
    static final TASK_OPTIONS = ['rebuild','integrateNewCommit']
}


//############################### SCRIPT SECTION ################################
echo "----------- Working on branch/tag ${params.branchOrTag} -----------"

if( params.target == '')
{
    params.target = pipeline
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

if( !TASK_OPTIONS.contains(params.task))
{
    echo "Error! Invalid value  \"${params.task}\" for job parameter task."
    throw new Exception('Invalid build-job parameter.')
}


// For unknown reasons, the repo url can not contain the second : after the machine name
// when used with the GitSCM class. So we remove it here.
parts = params.buildRepository.split(':')
def repository = parts[0] + ':' + parts[1] + parts[2]

def configurations = addRepositoryOperationsStage(repository, params.branchOrTag, task)
addPipelineStage(configurations, repository, params.branchOrTag, params.target)
addTaggingStage(repository, params.branchOrTag, taggingOption, taggedPackage)
addUpdateWebPageStage(repository, configurations, params.branchOrTag)


// Create a temporary branch that contains the the latest revision of the
// main branch (e.g. master) and merge the revisions into it that were pushed to
// the developer branch.
def addRepositoryOperationsStage( repository, branchOrTag, task)
{
    def usedConfigurations = []

    stage('Get Build-Configurations')
    {
        node(getDebianNodeLabel())
        {
            ws(getRepositoryName(repository))
            {
                checkoutBranch(repository, branchOrTag)

                // TODO
                // - update packages here.
                // - do code formating here.
                // - Make and push commit.

                // read the CiBuiltConfigurations.json file
                usedConfigurations = getBuildConfigurations()
            }
        }
    }

    return usedConfigurations
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

def addPipelineStage( cpfConfigs, repository, tagOrBranch, target)
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
            def myNode = createBuildNode( nodeLabel, config.ConfigName, repository, tagOrBranch, target, config?.CompilerConfig)
            parallelNodes[config.ConfigName] = myNode
            nodeIndex++
        }

        // run the nodes
        parallel parallelNodes
    }
}

def createBuildNode( nodeLabel, cpfConfig, repository, tagOrBranch, target, compilerConfig)
{
    return {
        node(nodeLabel)
        {
            // get the main name of repository

            
            ws("${getRepositoryName(repository)}-${cpfConfig}") 
            { 
                checkoutBranch(repository, tagOrBranch)

                dir(CHECKOUT_FOLDER)
                {
                    // Make the python scripts available in the root directory
                    runPythonCommand("Sources/CPFBuildscripts/0_CopyScripts.py")

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

def addTaggingStage(repository, branchOrTag, taggingOption, taggedPackage)
{
    if(taggingOption == 'noTagging')
    {
        return
    }

    stage('Integrate Tmp Branch')
    {
        node(getDebianNodeLabel())
        {
            ws(getRepositoryName(repository))
            {
                checkoutBranch(repository, branchOrTag)
                dir(CHECKOUT_FOLDER)
                {
                    // Merge the tmp branch into the main branch and tag it.
                    def releasedPackage = ""
                    if( taggingOption != 'internal' )
                    {
                        if( packages.size() > 1)
                        {
                            def packagesString = packages.join(';')
                            echo "When setting a release version, the packages option must contain at max one package name. The value was \"${packagesString}\"."
                            throw new Exception('Invalid value for build argument "packages".')
                        }
                        if(packages.size() == 1)
                        {
                            releasedPackage = packages[0]
                        }
                    }

                    sh "cmake -DROOT_DIR=\"\$PWD\" -DINCREMENT_VERSION_OPTION=${taggingOption} -DPACKAGE=\"${releasedPackage}\" -P Sources/${CPFCMAKE_DIR}/Scripts/addVersionTag.cmake"
                }
            }
        }
    }
}

def addUpdateWebPageStage(repository, cpfConfigs, branchOrTag)
{
    stage('Update Project Web-Page')
    {
        node('master')
        {
            ws(getRepositoryName(repository))
            {
                checkoutBranch(repository, branchOrTag) // get the scripts

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

                web_host = "root@${params.webserverHost}"

                // get the current html content from the web-server
                sh "scp -P 23 -r ${web_host}:/var/www/html/* \"${serverHtmlDir}\" || :" // || : suppresses the error message if the server html contains no files

                // merge the new html content into the old html content
                // sh "ls -l \$PWD/${CHECKOUT_FOLDER}/Sources/cmake/Scripts"
                sh "cmake -DSOURCE_DIR=\"${tempHtmlDir}\" -DTARGET_DIR=\"${serverHtmlDir}\" -DROOT_DIR=\"\$PWD/${CHECKOUT_FOLDER}\" -P \"\$PWD/${CHECKOUT_FOLDER}/Sources/${CPFCMAKE_DIR}/Scripts/updateExistingWebPage.cmake\""

                // copy the merge result back to the server
                sh "ssh -p 23 ${web_host} \"rm -rf /var/www/html/*\""
                sh "scp -P 23 -r \"${serverHtmlDir}\"/* ${web_host}:/var/www/html || :"
                
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

def addCreateReleaseTagStage(repository, incrementTaskType, branch)
{
    def usedConfigurations = []

    stage('Create Release Tag')
    {
        node('master')
        {
            ws(getRepositoryName(repository))
            {
                checkoutBranch(repository, branch)

                // execute the cmake script that does the git operations
                sh "cmake -DROOT_DIR=\"\$PWD/${CHECKOUT_FOLDER}\" -DBRANCH=${branch} -DDIGIT_OPTION=${incrementTaskType} -P \"\$PWD/${CHECKOUT_FOLDER}/Sources/${CPFCMAKE_DIR}/Scripts/incrementVersionNumber.cmake\""
            
                usedConfigurations = getBuildConfigurations()
            }
        }
    }

    return usedConfigurations
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