#!groovy

/**
The jenkins pipeline script for a CppCodeBase project.
*/

import static Constants.*
import groovy.json.JsonSlurper


//############################### SCRIPT SECTION ################################
echo "----------- Working on branch ${params.branchOrTag} -----------"

if( params.target == '')
(
    params.target = pipeline
)

// For unknown reasons, the repo url can not contain the second : after the machine name
// when used with the GitSCM class. So we remove it here.
parts = params.buildRepository.split(':')
def repository = parts[0] + ':' + parts[1] + parts[2]

if(params.task == 'integration')
{
    // Build a new commit and merge it into the main branch.

    // split branch name to get main branch
    // We assume here that the branch has a name of the from <developer>-int-<mainBranch>
    def pathParts = params.branchOrTag.split('/')
    def branchName = pathParts.last()
    def parts = branchName.split('-int-')
    def mainBranch = parts[1]
    def tempBranch = parts[0] + '-tmp-' + parts[1]
    def developer = parts[0]

    def configurations = addRepositoryOperationsStage(repository, mainBranch, true, developer)
    addPipelineStage(configurations, tempBranch, params.target)
    addUpdateMainBranchStage( developer, mainBranch, tempBranch)
    addUpdateWebPageStage(configurations, params.branchOrTag)
}
else if( params.task == 'rebuild' ) 
{
    // Rebuild an existing tag.
    //def configurations = addRepositoryOperationsStage(repository, params.branchOrTag, false, '')
    
    addRepositoryOperationsStage(repository, params.branchOrTag, false, '')


    def configurations = getBuildConfigurations()

    stage('Use information')
    {
        node('Windows-10-0.0.0-0'){
            ws('TempWorkspace')
            {   
                bat 'echo fuck yall 1'
            }
        }
    }

    /*
    addPipelineStage(configurations, repository, params.branchOrTag, params.target)
    addUpdateWebPageStage(configurations, params.branchOrTag)
    */
}
else if( params.task == 'incrementMajor' || params.task == 'incrementMinor' || params.task == 'incrementPatch' )
{
    // Add a release version tag and rebuild.
    def pathParts = params.branchOrTag.split('/')
    def branchName = pathParts.last()

    def configurations = addCreateReleaseTagStage(repository, params.task, branchName)
    addPipelineStage(configurations, branchName, params.target)
    addUpdateWebPageStage(configurations, params.branchOrTag)
}
else
{
    echo "Job parameter \"task\" has invalid value \"${params.task}\"."
}


//############################### FUNCTION SECTION ################################
class Constants {
    // locations
    static final WEBSERVER_HOST_NAME="root@172.19.0.2"      // This is defined by CppCodeBaseMachines
    static final CHECKOUT_FOLDER = 'Check out dir'
    static final CPPCODEBASECMAKE_DIR = 'CppCodeBaseCMake'

    // stash names
    static final HTML_STASH = "html"
}

// Create a temporary branch that contains the the latest revision of the
// main branch (e.g. master) and merge the revisions into it that were pushed to
// the developer branch.
def addRepositoryOperationsStage( repository, mainBranch, createTempBranch, developer)
{
    stage('Create Tmp Branch')
    {
        node('master')
        {
            ws('WS-CppCodeBase')
            {
                checkoutBranch(repository, params.branchOrTag)

                if(createTempBranch)
                {
                    // execute the cmake script that does the git operations and changes the source files
                    echo 'Create temporary build branch'
                    sh "cmake -DDEVELOPER=${developer} -DMAIN_BRANCH=${mainBranch} -DROOT_DIR=\"\$PWD/${CHECKOUT_FOLDER}\" -P \"\$PWD/${CHECKOUT_FOLDER}/Sources/${CPPCODEBASECMAKE_DIR}/Scripts/prepareTmpBranch.cmake\""
                }
            }
        }
    }
}

def getBuildConfigurations()
{
    node('master')
    {
        ws('WS-CppCodeBase')
        {
            // read the CiBuiltConfigurations.json file
            def fileContent = readFile(file:"${CHECKOUT_FOLDER}/Sources/CIBuildConfigurations.json")
            def configurations = new JsonSlurper().parseText(fileContent)
            def usedConfigurations = []
            if( params.ccbConfiguration != '')
            {
                for(config in configurations)
                {
                    if(config.ConfigName == params.ccbConfiguration)
                    {
                        usedConfigurations.add(config)
                    }
                }
            }
            else
            {
                usedConfigurations = configurations
            }

            return usedConfigurations
        }
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

    /*
    deleteDir()
    runCommand("git clone --recursive ${repository} \"${CHECKOUT_FOLDER}\"")

    dir(CHECKOUT_FOLDER){
        runCommand("git checkout ${branch}")
        runCommand("git submodule update")
    }
    */
}

def addPipelineStage( ccbConfigs, repository, tempBranch, target)
{
    stage('Build Pipeline')
    {
        def parallelNodes = [:]
        parallelNodes.failFast = true
        
        // add nodes for building the pipeline
        def nodeIndex = 0
        for(config in ccbConfigs)
        {
            echo "Create build node " + config
            def nodeLabel = config.BuildSlaveLabel + '-' + nodeIndex
            echo "Build ${config.ConfigName} under label ${nodeLabel}"
            def myNode = createBuildNode( nodeLabel, config.ConfigName, repository, tempBranch, target, config?.CompilerConfig)
            parallelNodes[nodeLabel] = myNode
            nodeIndex++
        }

        // run the nodes
        parallel parallelNodes
    }
}

def createBuildNode( nodeLabel, ccbConfig, repository, builtTagOrBranch, target, compilerConfig)
{
    return { 
        node(nodeLabel)
        {
            /*
            ws(ccbConfig)
            {   

                checkoutBranch(repository, builtTagOrBranch)

                dir(CHECKOUT_FOLDER)
                {
                    // Make the python scripts available in the root directory
                    runPythonCommand("Sources/CppCodeBaseBuildscripts/0_CopyScripts.py")

                    // Setup build configurations
                    // We do not use the ninja build-system for msvc because ninja in combination with mscv can randomly fail with an error thet says that a .pdb file could not be opened.
                    // This usually does not happen when doing a fresh build, but rather when doing incremental builds.
                    // https://github.com/ninja-build/ninja/issues/620
                    runPythonCommand("1_Configure.py ${ccbConfig} --inherits ${ccbConfig}")
                    
                    // generate makefiles
                    runPythonCommand("2_Generate.py ${ccbConfig}")

                    // build the pipeline target
                    def configOption = ''
                    if(compilerConfig) // The build config option is only needed for multi-config generators.
                    {
                        configOption = "--config ${compilerConfig}"
                    }
                    runXvfbWrappedPythonCommand( "3_Make.py ${ccbConfig} --target ${target} ${configOption}" )

                    // stash generated html content
                    dir( "Generated/${ccbConfig}" )
                    {
                        def htmlStash = "${HTML_STASH}${ccbConfig}"
                        stash includes: 'html/**', name: htmlStash
                    }
                    
                    echo "----- The pipeline finished successfully for configuration ${ccbConfig}. -----"
                }
            }
            */
        }
    }
}

def addUpdateMainBranchStage( repository, developer, mainBranch, tempBranch)
{
    stage('Integrate Tmp Branch')
    {
        node('Debian-8.9')
        {
            ws('WS-CppCodeBase')
            {
                checkoutBranch(repository, tempBranch)
                dir(CHECKOUT_FOLDER)
                {
                    // TODO Add format target, build it and commit the changes.

                    // Merge the tmp branch into the main branch and tag it.
                    sh "cmake -DDEVELOPER=${developer} -DMAIN_BRANCH=${mainBranch} -DROOT_DIR=\"\$PWD\" -P Sources/${CPPCODEBASECMAKE_DIR}/Scripts/integrateTmpBranch.cmake"
                
                    echo "----- The commits from branch ${params.branchOrTag} were successfully integrated into the main branch. -----"
                }
            }
        }
    }
}

def addUpdateWebPageStage(repository, ccbConfigs, branchOrTag)
{
    stage('Update Project Web-Page')
    {
        node('master')
        {
            ws('WS-CppCodeBase')
            {
                checkoutBranch(repository, branchOrTag) // get the scripts

                def serverHtmlDir = '$PWD/html-on-server'
                def tempHtmlDir = '$PWD/html'
                
                // make sure previous content of the html directory is removed.
                sh "cmake -E remove_directory \"${serverHtmlDir}\""
                sh "mkdir \"${serverHtmlDir}\""
                sh "cmake -E remove_directory \"${tempHtmlDir}\""
            
                // collect all produced html content from the build-slaves
                for(ccbConfig in ccbConfigs)
                {
                    unstashFiles(HTML_STASH, ccbConfig.ConfigName)
                }
                // sh "ls -l \"${tempHtmlDir}\""

                // get the current html content from the web-server
                sh "scp -r ${WEBSERVER_HOST_NAME}:/var/www/html/* \"${serverHtmlDir}\" || :" // || : suppresses the error message if the server html contains no files

                // merge the new html content into the old html content
                // sh "ls -l \$PWD/${CHECKOUT_FOLDER}/Sources/cmake/Scripts"
                sh "cmake -DSOURCE_DIR=\"${tempHtmlDir}\" -DTARGET_DIR=\"${serverHtmlDir}\" -DROOT_DIR=\"\$PWD/${CHECKOUT_FOLDER}\" -P \"\$PWD/${CHECKOUT_FOLDER}/Sources/${CPPCODEBASECMAKE_DIR}/Scripts/updateExistingWebPage.cmake\""

                // copy the merge result back to the server
                sh "ssh ${WEBSERVER_HOST_NAME} \"rm -rf /var/www/html/*\""
                sh "scp -r \"${serverHtmlDir}\"/* ${WEBSERVER_HOST_NAME}:/var/www/html || :"
                
                echo '----- The project web-page was updated successfully. -----'
            }
        }
    }
}

def addCreateReleaseTagStage(repository, incrementTaskType, branch)
{
    stage('Create Release Tag')
    {
        node('master')
        {
            ws('WS-CppCodeBase')
            {
                checkoutBranch(repository, branch)

                // execute the cmake script that does the git operations
                sh "cmake -DROOT_DIR=\"\$PWD/${CHECKOUT_FOLDER}\" -DBRANCH=${branch} -DDIGIT_OPTION=${incrementTaskType} -P \"\$PWD/${CHECKOUT_FOLDER}/Sources/${CPPCODEBASECMAKE_DIR}/Scripts/incrementVersionNumber.cmake\""
            }
        }
    }
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
    runCommand(os, pythonCmd + ' ' + command)
}

def getPythonCommand(os)
{
    pythonVersion = sh(returnStdout: true, script: 'python --version').trim()
    def pythonCmd = 'python'
    if(!version.matches(~'^3\\..*$'))
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

def cleanWorkspace()
{
    echo 'Clean Workspace ...'
    dir('WS-CppCodeBase'){
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