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

    createTempBranch( developer, mainBranch)
    addPipelineStage( toolchains, tempBranch, params.target)
    addUpdateMainBranchStage( developer, mainBranch, tempBranch)
    addUpdateWebPageStage( toolchains, params.branchOrTag)
}
else if( params.task == 'rebuild' ) 
{
    // Rebuild an existing tag.

    addPipelineStage(toolchains, params.branchOrTag, params.target)
    addUpdateWebPageStage(toolchains, params.branchOrTag)
}
else if( params.task == 'incrementMajor' || params.task == 'incrementMinor' || params.task == 'incrementPatch' )
{
    // Add a release version tag and rebuild.
    def pathParts = params.branchOrTag.split('/')
    def branchName = pathParts.last()

    addCreateReleaseTagStage( params.task, branchName)
    addPipelineStage( toolchains, branchName, params.target)
    addUpdateWebPageStage( toolchains, params.branchOrTag)
}
else
{
    echo "Job parameter \"task\" has invalid value \"${params.task}\"."
}

//############################### FUNCTION SECTION ################################
class Constants {
    // config names
    static final VS2015DEBUG = "VS2015Debug"
    static final VS2015RELEASE = "VS2015Release"
    static final GCCDEBUG = "GCCDEBUG"
    static final CLANGRELEASE = "CLANGRELEASE"

    // locations
    static final REPOSITORY_HOST_NAME="admin@datenbunker"
    static final WEBSERVER_HOST_NAME="root@172.19.0.2"
    static final CHECKOUT_FOLDER = 'Check out dir'
    static final CPPCODEBASECMAKE_DIR = 'CppCodeBaseCMake'

    // stash names
    static final HTML_STASH = "html"
}

def getCcbConfigurations()
{
    if( params.ccbConfiguration == '')
    {
        // read the CiBuiltConfigurations.json file
        def configFile = new File("${CHECKOUT_FOLDER}/Sources/CIBuildConfigurations.json")
        def InputJSON = new JsonSlurper().parse(configFile)
        InputJSON.each{ println it }
    }
    else
    {
        return params.ccbConfiguration
    }
}

// Create a temporary branch that contains the the latest revision of the
// main branch (e.g. master) and merge the revisions into it that were pushed to
// the developer branch.
def createTempBranch( developer, mainBranch)
{
    stage('Create Tmp Branch')
    {
        node('master')
        {
            ws('WS-CppCodeBase')
            {
                checkoutBranch(params.branchOrTag)

                // execute the cmake script that does the git operations and changes the source files
                echo 'Create temporary build branch'
                sh "cmake -DDEVELOPER=${developer} -DMAIN_BRANCH=${mainBranch} -DROOT_DIR=\"\$PWD/${CHECKOUT_FOLDER}\" -P \"\$PWD/${CHECKOUT_FOLDER}/Sources/${CPPCODEBASECMAKE_DIR}/Scripts/prepareTmpBranch.cmake\""
            }
        }
    }
}

def addPipelineStage( ccbConfigs, tempBranch, target, ccbConfiguration)
{
    stage('Build Pipeline')
    {
        def parallelNodes = [:]
        parallelNodes.failFast = true
        
        // add nodes for building the pipeline
        def nodeIndex = 0
        for(toolchain in toolchains)
        {
            echo "Create build node " + toolchain
            def nodeLabel = getBaseNodeLabelForToolchain(toolchain, nodeIndex)
            echo "Build ${toolchain} under label ${nodeLabel}"
            def myNode = createBuildNode( nodeLabel, toolchain, tempBranch, target)
            parallelNodes[nodeLabel] = myNode
            nodeIndex++
        }

        // run the nodes
        parallel parallelNodes
    }
}

def createBuildNode( nodeLabel, ccbConfig, builtTagOrBranch, target)
{
    return { 
        node(nodeLabel)
        {
            // acquiering an extra workspace seems to be necessary to prevent interaction between
            // the parallel run nodes, although node() should already create an own workspace.
            ws(toolchain)   
            {   
                checkoutBranch(builtTagOrBranch)

                dir(CHECKOUT_FOLDER)
                {
                    // define the project configurations that are tested on the buildserver.
                    def configOption = ''
                    
                    // Make the python scripts available in the root directory
                    runPythonCommand(toolchain, "Sources/CppCodeBaseBuildscripts/0_CopyScripts.py")

                    // Setup build configurations
                    // We do not use the ninja build-system for msvc because ninja in combination with mscv can randomly fail with an error thet says that a .pdb file could not be opened.
                    // This usually does not happen when doing a fresh build, but rather when doing incremental builds.
                    // https://github.com/ninja-build/ninja/issues/620
                    switch(toolchain)
                    {
                        case VS2015RELEASE:
                            runPythonCommand(toolchain, "1_Configure.py ${toolchain} --inherits Windows")
                            configOption = '--config Release'
                            break
                        case VS2015DEBUG:
                            // Here we also test building the production libraries as shared libraries
                            // This configuration runs the OpenCppCoverage dynamic analysis because uses the debug mode.
                            runPythonCommand(toolchain, "1_Configure.py ${toolchain} --inherits VS2015-shared")
                            configOption = '--config Debug'
                            break
                        case GCCDEBUG:
                            // we use the gcc config to test if the project builds without precompiled headers, to make sure that all files include what they need.
                            runPythonCommand(toolchain, "1_Configure.py ${toolchain} --inherits Gcc-shared-debug")
                            break
                        case CLANGRELEASE:
                            // This configuration will run the valgrind dynamic analysis because it used debug options.
                            runPythonCommand(toolchain, "1_Configure.py ${toolchain} --inherits Clang-static-release")
                            break
                        default:
                            echo "Default case in getOsFromToolchain() for argument ${toolchain}"
                            assert false
                    }
                    
                    // generate makefiles
                    runPythonCommand(toolchain, "2_Generate.py ${toolchain}")

                    // build the pipeline target
                    runXvfbWrappedPythonCommand( toolchain, "3_Make.py ${toolchain} --target ${target} ${configOption}" )

                    // stash generated html content
                    dir( "Generated/${toolchain}" )
                    {
                        def htmlStash = "${HTML_STASH}${toolchain}"
                        stash includes: 'html/**', name: htmlStash
                    }
                    
                    echo "----- The pipeline finished successfully for configuration ${toolchain}. -----"
                }
            }
        }
    }
}

def addUpdateMainBranchStage( developer, mainBranch, tempBranch)
{
    stage('Integrate Tmp Branch')
    {
        node('Debian-8.9')
        {
            ws('WS-CppCodeBase')
            {
                checkoutBranch(tempBranch)
                dir(CHECKOUT_FOLDER)
                {
                    // TODO Add format target and reactivate this code.

                    // Build the format target and commit the code changes.
                    /*
                    def toolchain = GCCDEBUG
                    runPythonCommand(toolchain, "0_Configure.py ${toolchain} --inherits Gcc-shared-debug")
                    runPythonCommand(toolchain, "1_Generate.py ${toolchain}")
                    runPythonCommand(toolchain, "2_Make.py ${toolchain} --target format")

                    // Commit the changed source files.
                    sh "git commit . -m\"Version update and formatting for integration of branch ${params.branch}.\" || :"
                    sh 'git push || :'
                    */

                    // Merge the tmp branch into the main branch and tag it.
                    sh "cmake -DDEVELOPER=${developer} -DMAIN_BRANCH=${mainBranch} -DROOT_DIR=\"\$PWD\" -P Sources/${CPPCODEBASECMAKE_DIR}/Scripts/integrateTmpBranch.cmake"
                
                    echo "----- The commits from branch ${params.branchOrTag} were successfully integrated into the main branch. -----"
                }
            }
        }
    }
}

def addUpdateWebPageStage(ccbConfigs, branchOrTag)
{
    stage('Update Project Web-Page')
    {
        node('master')
        {
            ws('WS-CppCodeBase')
            {
                checkoutBranch(branchOrTag) // get the scripts

                def serverHtmlDir = '$PWD/html-on-server'
                def tempHtmlDir = '$PWD/html'
                
                // make sure previous content of the html directory is removed.
                sh "cmake -E remove_directory \"${serverHtmlDir}\""
                sh "mkdir \"${serverHtmlDir}\""
                sh "cmake -E remove_directory \"${tempHtmlDir}\""
            
                // collect all produced html content from the build-slaves
                for(toolchain in toolchains)
                {
                    unstashFiles(HTML_STASH, toolchain)
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

def addCreateReleaseTagStage( incrementTaskType, branch)
{
    stage('Create Release Tag')
    {
        node('master')
        {
            ws('WS-CppCodeBase')
            {
                checkoutBranch(branch)

                // execute the cmake script that does the git operations
                sh "cmake -DROOT_DIR=\"\$PWD/${CHECKOUT_FOLDER}\" -DBRANCH=${branch} -DDIGIT_OPTION=${incrementTaskType} -P \"\$PWD/${CHECKOUT_FOLDER}/Sources/${CPPCODEBASECMAKE_DIR}/Scripts/incrementVersionNumber.cmake\""
            }
        }
    }
}

def checkoutBranch(branch)
{
    checkout([$class: 'GitSCM',
            userRemoteConfigs: [[url: "ssh://${REPOSITORY_HOST_NAME}/share/GitRepositories/BuildCppCodeBaseAssistant.git"]],
            branches: [[name: branch]],
            // We checkout to a subdirectory so the folders for the test files that lie parallel to the repository are still within the workspace.
            extensions: [
                [$class: 'CleanBeforeCheckout'],
                [$class: 'RelativeTargetDirectory', 
                    relativeTargetDir: CHECKOUT_FOLDER],
                [$class: 'SubmoduleOption', 
                    diableSubmodules: false, 
                    parentCredentials: false, 
                    recursiveSubmodules: true, 
                    reference: '', 
                    trackingSubmodules: false ]],
            submoduleCfg: []
        ]
    )
}

def unstashFiles(String stashName, String toolchain)
{
    def fullStashName = stashName + toolchain
    echo "Unstash files from stash: " + fullStashName
    unstash fullStashName
}

def runPythonCommand(ccbConfigOrOs, command)
{
    def os = ''
    if(toolchainOrOs == 'linux' || toolchainOrOs == 'windows')
    {
        os = toolchainOrOs
    }
    else
    {
        os = getOsFromToolchain(toolchainOrOs)
    }

    def pythonCmd = getPythonCommandForOs(os)
    runCommand(os, pythonCmd + ' ' + command)
}

def getPythonCommandForOs(os)
{
    def pythonCmd = 'python'
    if(os == 'linux')
    {
        pythonCmd = 'python3'
    }
    return pythonCmd
}

def runCommand(os, command)
{
    echo "runCommand(" + os + "," + command + ")"
    if(os == 'windows')
    {
        bat command
    }
    else if( os == 'linux')
    {
        sh command
    }
}

def getOsFromToolchain(toolchain)
{
    switch(toolchain)
    {
        case VS2015RELEASE:
        case VS2015DEBUG:
            return 'windows'
        case GCCDEBUG:
        case CLANGRELEASE:
            return 'linux'
        case "NotUsed":
            return 'master'
        default:
            echo 'Default case in getOsFromToolchain() for argument ' + toolchain
            assert false
    }
}

def runXvfbWrappedPythonCommand(toolchain, command)
{
    def isLinux = getOsFromToolchain(toolchain) == 'linux'
    if(isLinux)
    {
        // On linux we need the jenkins Xvfb plugin to simulate an x11 server or qt will give us errors that it can not connect to the x11 server.
        wrap([$class: 'Xvfb', parallelBuild: true, displayNameOffset: 1, autoDisplayName: true, assignedLables: 'linux'])
        {
            runPythonCommand(toolchain, command)
        }
    }
    else
    {
        runPythonCommand(toolchain, command)
    }
}

def getBaseNodeLabelForToolchain(toolchain, index)
{
    def os = getOsFromToolchain(toolchain)
    if(os == 'windows')
    {
        return "Windows-10-${index}"
    }
    else if(os == 'linux')
    {
        return "Debian-8.9-${index}"
    }
}

def cleanWorkspace()
{
    echo 'Clean Workspace ...'
    dir('CppCodeBase'){
        deleteDir()
    }
}

def showTree(toolchain)
{
    def os = getOsFromToolchain(toolchain)
    if(os == 'windows')
    {
        bat 'tree /F /A'
    }
    else if(os == 'linux')
    {
        sh 'tree'
    }
}
