#!/bin/bash
###############################################################################
# Common Script Elements shared by the build script in this directory and the
# build script in the appliance sub-directory. 
# This script is also used by the CI build system.
# @author: oazmon
###############################################################################
#
# -----------------------------------------------------------------------------
# Initializing variables
# -----------------------------------------------------------------------------
# OS Name
os=`uname`

if [ ! -z "$DEBUG" ]; then
    log_level+=("debug")
fi
if [ ! -z "$TRACE" ]; then
    log_level+=("trace debug")
fi
if [[ "${log_level[@]}" =~ "trace" ]]; then
    set -x
fi

#------------------------------------------------------------------------------
# Function that logs to standard out like log4j
# Usage: log "[level]" "[text]"
#------------------------------------------------------------------------------
function log() {
  if [[ "${log_level[@]}" =~ "${1}" ]]; then
    echo "[`date '+%Y-%m-%d %H:%M:%S'`] | ${1} | ${2}" 
  fi
}

#------------------------------------------------------------------------------
# Function that echo a command and then executes it
# Usage: echo_exec [cmd]
#------------------------------------------------------------------------------
function echo_exec() {
    CALL_CMD="$*"
    log "info" "${CALL_CMD}"
    ${CALL_CMD}
}

#------------------------------------------------------------------------------
# General hosting information.  Add as needed to help troubleshoot build issues.
#------------------------------------------------------------------------------
function show_hosting_info() {
    set_e "off"
    log "info" ":::::::::::::::::::::::: `date +%H:%M:%S` beginning build host information \"$0\""

    # some system info
    if [ X"$os" = X"Darwin" ]; then
        log "info" ":::::::::::::::::::::::: hostname for OS/X:"
        hostname -f
    else
        log "info" ":::::::::::::::::::::::: hostname, including FQDN and all IP addresses:"
        hostname --fqdn
        hostname -a
        hostname --all-ip-addresses
    fi
    log "info" ":::::::::::::::::::::::: uname -a"
    uname -a
    if [ -r "/proc/version" ] ; then
        log "info" ":::::::::::::::::::::::: contents of /proc/version:"
        cat /proc/version
    fi
    if [ -r "/etc/redhat-release" ] ; then
        log "info" ":::::::::::::::::::::::: contents of /etc/redhat-release:"
        cat /etc/redhat-release
    elif [ -r "/etc/os-release" ] ; then
        log "info" ":::::::::::::::::::::::: contents of /etc/os-release:"
        cat /etc/os-release
    elif [ X"$os" = "Linux" ] ; then
        log "info" ":::::::::::::::::::::::: hmmm.... anything matching /etc/\*-release that might tell us about the OS\?"
        ls -l /etc/*-release
    fi
   
    log "info" ":::::::::::::::::::::::: env"
    env
     
    echo :::::::::::::::::::::::: pwd, ls -la, df -h
    pwd
    pwd -P
    ls -la
    df -h
    
    echo :::::::::::::::::::::::: uptime, ntpstat, date
    uptime
    if ! ntpstat 2>&1 ; then
        echo problem with ntpstat \($?\)
    fi
    date '+%Y-%m-%d %H:%M:%S -- TZ: %Z %:z -- year# %G week# %V day# %j'
    
    echo :::::::::::::::::::::::: envars w/o secrets, passwords, or tokens
    printenv | grep -vi -e pass -e secret -e token | sort
    
    echo :::::::::::::::::::::::: about git: which, version, and status
    which git
    git --version
    git status
    
    echo :::::::::::::::::::::::: git log --pretty=oneline --abbrev-commit --graph --decorate --max-count=10
    git log --pretty=oneline --abbrev-commit --graph --decorate --max-count=10 | cat
    
    echo :::::::::::::::::::::::: about java, javac: which + version
    which java
    java -version 2>&1
    which javac
    javac -version 2>&1
    
    log "info" ":::::::::::::::::::::::: `date +%H:%M:%S` ending build host information \"$0\""
    reset_e
}

#------------------------------------------------------------------------------
# Function that runs an echo_exec in the current context and in the specified 
# directory and returns without changing directories
# Usage: run_id [directory cmd]
#------------------------------------------------------------------------------
function run_in() {
  (cd $1; shift 1; echo_exec $*)
}

#------------------------------------------------------------------------------
# Function to parse simple XML
# Usage: read_entity [key]
#------------------------------------------------------------------------------
read_entity() {
    while read_dom; do
        if [[ $ENTITY = "$1" ]]; then
            echo $CONTENT
            exit
        fi
    done
}

# Helper for read_entity
read_dom () {
    local IFS=\>
    read -d \< ENTITY CONTENT
}

#------------------------------------------------------------------------------
# Function that fetch an artifact from Nexus
# Assumes NEXUS_URL points to the Nexus instance to use.
# Usage: nexus_fetch_gav [GAV]
#      Where GAV is groupId:artifactId:version
#          or groupId:artifactId:packaging:classifier:version
#------------------------------------------------------------------------------
function nexus_fetch_gav() {
    local IFS=":"
    local gav_coord=( $1 )
    if [ ${#gav_coord[@]} -eq 3 ]; then
        local group_id=${gav_coord[0]}
        local artifact_id=${gav_coord[1]}
        local packaging=
        local classifier=
        local version=${gav_coord[2]}     
    else
        local group_id=${gav_coord[0]}
        local artifact_id=${gav_coord[1]}
        local packaging=${gav_coord[2]}  
        local classifier=${gav_coord[3]}  
        local version=${gav_coord[4]}
    fi

    local param_keys=( g a v p c )
    local param_values=( $group_id $artifact_id $version $packaging $classifier )
    local query_params=""
    local params=""
    for index in ${!param_keys[*]}; do
        if [[ X"${param_values[$index]}" != X"" ]]; then
            if [ X"${param_keys[$index]}" != X"p" ]; then
                local query_params="${query_params}${param_keys[$index]}=${param_values[$index]}&"
            fi
            local params="${params}${param_keys[$index]}=${param_values[$index]}&"
        fi
    done
    IFS=" "
    
    # Query the repo where the artifact is located
    CMD="curl -sS -L ${NEXUS_URL}/service/local/lucene/search?count=1&${query_params}"
    log "info" "${CMD}"
    response=` ${CMD} `
    repo=` echo ${response} | read_entity "repositoryId" `
    if [ ! -z $repo ]; then
        log "debug" "$artifact_id was found in repo: '${repo}'"
    else
        log "error" "Artifact was NOT found any repo: [artifact_id=$artifact_id]"
        exit 1
    fi

    # Fetch the artifact
    if [ ! -z "${2}" ]; then
       target_dir="${2}/"
    fi
    echo_exec curl -sS -L "${NEXUS_URL}/service/local/artifact/maven/content?r=$repo&${params}" -o "${target_dir}${artifact_id}.${packaging:-jar}"    
}

#------------------------------------------------------------------------------
# Function that parse a YAML file into a Sparse Bash Array
# Usage: read -r -a ${array_name} <<<$(parse_yaml ${filename})
#    where:
#        array_name is the resulting array name
#        filename is the name of the file to parse
#------------------------------------------------------------------------------
parse_yaml() {
    local s='[[:space:]]*' w='[a-zA-Z0-9_]*' fs=$(echo @|tr @ '\034')
    sed -ne "s|^\($s\)\($w\)$s:$s\"\(.*\)\"$s\$|\1$fs\2$fs\3|p" \
            -e "s|^\($s\)\($w\)$s:$s\(.*\)$s\$|\1$fs\2$fs\3|p"  $1 |
    awk -F$fs '{
        indent = length($1)/2
        vname[indent] = $2
        for (i in vname) {
            if (i > indent) {
                delete vname[i]
            }
        }
        if (length($3) > 0) {
            vn=""
            for (i=0; i<indent; i++) {
                vn=(vn)(vname[i])(".")
            }
            printf("%s%s=\"%s\"\n", vn, $2, $3);
        }
    }'
}

#------------------------------------------------------------------------------
# Get all the keys in the array. The array of keys found is echoed to 
# standard out 
# Usage: get_array_keys ${filter}
#    where:
#        filter is an optional regex pattern to filter the keys
#------------------------------------------------------------------------------
function get_array_keys() {
    eval work_array=\${${1}[@]}
    local keys=()
    for entry in ${work_array[@]}; do
        key=${entry%%=*}
        if [[ ${key} =~ ${2} ]]; then
           keys+=(${key})
        fi
    done
    echo ${keys[@]}
}

#------------------------------------------------------------------------------
# Function that gets a value from a Sparse Bash Array such a the one created
# by the parse_yaml function.  The value is echoed to standard out. If not
# found an empty string is echoed.
# Usage: get_array_value ${array_name} ${value_name}
#    where:
#        array_name is the array name to search
#        value_name is the name of the value to search
# value.
#------------------------------------------------------------------------------
function get_array_value() {
    eval work_array=\${${1}[@]}
    for entry in ${work_array[@]}; do
        KEY=${entry%%=*}
        if [ X"$KEY" = X"${2}" ]; then
           eval echo ${entry#*=}
        fi
    done
    echo ""
}


#------------------------------------------------------------------------------
# Function that updates a Sparse Bash Array key values pairs, by prompting the
# user with a key and its current value and allowing him/her to update.
# After all values are updated the user is asked to confirm.
# Usage: get_array_values_from_user ${key_value_pair_array}
#    where:
#        key_value_pair_array is the array name to update
#------------------------------------------------------------------------------
function get_array_values_from_user() {
    set_e "off"
    eval value_count=\$\(expr \${#${1}[@]} - 1\)
    reset_e
    while true; do
        for i in $(eval echo "{0..$value_count}"); do 
            eval item=\${${1}[\$i]}
            key=${item%%=*}
            value=${item#*=}
            echo -n "Enter ${key} (current value=${value}): "
            read newValue
            if [ ! -z "$newValue" ]; then
                # Do special input validation based on the input key
                case ${key} in
                    "teamEmail" )
                        # Don't translate any characters in the email
                        ;;
                    "devAwsAccount" )
                        # Remove dashes from AWS account number
                        newValue=$(echo "$newValue" | tr -cd '[[:digit:]]')
                        ;;
                    * )
                        # Remove all non-alphanumeric characters, except dash ('-')
                        newValue=$(echo "$newValue" | tr -cd '[[:alnum:]]-')
                        ;;
                esac

                eval ${1}[\$i]="\${key}=\${newValue}"
            fi
        done

        echo ""
        echo "Got:"
        for item in $(eval echo \${${1}[@]}); do 
            echo "    ${item}"
        done
        echo ""
        echo "Okay to Update?"
        select yn in "Ok to Update" "Correct Values" "Cancel"; do
            case $yn in
               Ok\ to\ Update ) echo "updating"; return 0;;
               Correct\ Values ) break;;
               Cancel ) return -1;;
               * ) echo "Please select an option Number"
            esac
        done
    done
}


# used by set_e and reset_e function
e_state_array=()

#------------------------------------------------------------------------------
# Function that sets the '-e' option and remembers what it was by maintaining
# a stack of prior values. Works with reset_e function.
# Usage: set_e {state}
#    where:
#        state is "on" or "off"
#------------------------------------------------------------------------------
function set_e() {
    if [[ $- =~ e ]]; then
       e_state_array+=("on")
    else
       e_state_array+=("off")
    fi
    if [ ${1} == "on" ]; then
       set -e
    else
       set +e
    fi
}

#------------------------------------------------------------------------------
# Function that resets the '-e' option to a value remember during a call to the
# set_e function.
# Usage: reset_e
#------------------------------------------------------------------------------
function reset_e() {
    state_count=${#e_state_array[@]}
    last=` expr $state_count - 1 ` || true
    last_e_state=(${e_state_array[$last]})
    e_state_array=(${e_state_array[@]:0:$last})
    if [ "${last_e_state}" == "on" ]; then
       set -e
    else 
       set +e
    fi
}

#------------------------------------------------------------------------------
# Function that finds a file by searching in the current directory and in each
# parent directory.
# Usage: find_file_up_tree {file_name}
#    where file_name is the file to find
# Returns the fully qualified path of the file found or nothing.
#------------------------------------------------------------------------------
function find_file_up_tree() {
   path=$(pwd)
   while [ ! -f $path/${1} ]; do
      if [ "$path" = "/" ]; then
          return -1
      fi
      path=$(dirname $path)
   done
   echo $path/${1}
   return 0
}


#------------------------------------------------------------------------------
# Function locate and/or installs the eiamCli and update the PATH as needed.
# Usage: get_eiam
#------------------------------------------------------------------------------
function get_eiam() {
    set_e "off"
    type eiamCli >/dev/null 2>&1
    exit_code=$?
    reset_e
    if [ ${exit_code} -eq 0 ]; then
        log "debug" "eiamCli found in PATH"
    elif [ -x /usr/local/bin/eiamCli ]; then
        log "debug" "eiamCli found in /usr/local/bin"
        export PATH=$PATH:/usr/local/bin
    elif [ -x $HOME/.bin/eiamCli ]; then
        log "debug" "eiamCli found in ~/.bin"
        export PATH=$PATH:$HOME/.bin
    else
        NEXUS_URL=http://nexus.corp.intuit.net/nexus
        nexus_fetch_gav com.intuit.eiam:EIAM_CLI-mac:zip::1.1.3 /tmp
        unzip ${target_dir}EIAM_CLI-mac.zip ${install_dir} -d /tmp
        mkdir -p $HOME/.bin
        mv /tmp/eiamCli/eiamCli $HOME/.bin/eiamCli
        rm -fr /tmp/eiamCli
        rm ${target_dir}EIAM_CLI-mac.zip
        export PATH=$PATH:$HOME/.bin
    fi
}

#------------------------------------------------------------------------------
# Function that gets the AWS credentials for any *_aws_account listed in the 
# vars.yaml file and places them in the matching *_aws_profile profile. The 
# credentials are fetched using eiamCli.
# Usage: get_aws_credentials
#------------------------------------------------------------------------------
function get_aws_credentials() {
    local vars_yaml_array=${1}
    local target_env=${2:-""}
    if [ -z ${target_env} ]; then
        local key_list=$(get_array_keys ${vars_yaml_array} '\.*_aws_account')
    else
        local key_list=$(get_array_keys ${vars_yaml_array} "${target_env}_aws_account")
    fi
    for key in ${key_list}; do
        env=${key%_aws_account}
        aws_account=$(get_array_value ${vars_yaml_array} "${env}_aws_account" | tr -d '-')
        aws_profile=$(get_array_value ${vars_yaml_array} "${env}_aws_profile")
        region=$(get_array_value ${vars_yaml_array} "${env}_region")
        if [ -z ${aws_profile} ]; then
            log "error" "Missing profile name: [aws_account=${aws_account}]"
            return -1
        fi
        set_e "off"
        local output_file=$(mktemp)
        eiamCli getAWSTempCredentials -a ${aws_account} -r PowerUser -o 1 -p ${aws_profile} | tee -ai ${output_file}
        grep -q 'Your AWS Temporary keys were successfully written' ${output_file}
        error_code=$?
        reset_e
        # if 'Authentication failed' found, return failure
        if [ $error_code -ne 0 ]; then
            log "error" "Failed to get PowerUser AWS Credentials: [aws_account=${aws_account} profile=${aws_profile}]"
            return -1
        fi
        aws configure set profile.${aws_profile}.region ${region}
        aws configure set profile.${aws_profile}.s3.signature_version s3v4
        log "info" " Got PowerUser AWS Credentials: [aws_account=${aws_account} aws_profile=${aws_profile}]"
    done
    return 0
}

#------------------------------------------------------------------------------
# Obtain EIAM Credentials
#------------------------------------------------------------------------------
function obtain_credentials() {
    local vars_yaml_array=${1}
    local target_env=${2:-""}

    # Assume we are not interactive and so the caller must fetch creds
    if [ ! -z "${BATCH}" ]; then
        log "info" "--------------------------------------------------------------------------------"
        log "info" " Batch Run assume Credentials setup"
        log "info" "--------------------------------------------------------------------------------"
        return 0
    fi   

    log "info" "--------------------------------------------------------------------------------"
    log "info" " Obtaining AWS Credentials"
    log "info" "--------------------------------------------------------------------------------"
    get_eiam

    set_e "off"
    get_aws_credentials ${vars_yaml_array} ${target_env}
    exit_code=$?
    reset_e
    if [ $exit_code -ne 0 ]; then
       echo ""
       echo "Please Login with your corporate credentials"
       eiamCLI login
       get_aws_credentials ${vars_yaml_array} ${target_env}
    fi
}

#------------------------------------------------------------------------------
# Function that creates a key-value pair array using *_vpc_name from the 
# vars.yaml file as the key, the matching vpc_id as the value.
# Matches are found by search the aws account using the credentials in 
# the matching *_aws_profile.
# Usage: make_vpc_id_array {vars_yaml_array} {key-value-pair-array-name}
#    where: 
#        vars_yaml_array is the name of the array with the loaded content
#            of the vars.yaml file
#        key-value-pair-array-name is the name of the array where the 
#            the results are placed         
#------------------------------------------------------------------------------
function make_vpc_id_array() {
    eval vars_yaml_array=\${${1}[@]}
    eval ${2}=\(\)
    for key in $(get_array_keys vars_yaml_array '\.*_vpc_name'); do
        local vpc_name=$(get_array_value vars_yaml_array "${key}")
        local env=${key%_vpc_name}
        log "debug" "Processing vpc_name=$vpc_name in env=${env}"
        local vpc_id_key="${env}_vpc_id"
        local vpc_id=$(get_array_value vars_yaml_array "${vpc_id_key}")
        log "debug" "Found in vars.yaml that ${vpc_id_key}=$vpc_id"
        get_aws_vpc_id "${vars_yaml_array}" ${env} ${vpc_name} aws_vpc_id
        log "debug" "Found AWS vpc_id=$aws_vpc_id"
        if [ -z ${vpc_id} ]; then
            eval ${2}+=\(\${vpc_id_key}=\${aws_vpc_id}\)
        elif [ "${vpc_id}" != "${aws_vpc_id}" ]; then
            log "error" "vpc_id mismatch between AWS and VARS file: [VARS_FILE=${VARS_FILE} aws_vpc_id=${aws_vpc_id} ${vpc_id_key}=${vpc_id}]"
            return -1
        fi
    done
    return 0
}

#------------------------------------------------------------------------------
# Function that services make_vpc_id_array by fetching a vpc_id from AWS.
# Usage: get_aws_vpc_id {vars_yaml_array} {env} {vpc_name} {result_name}
#    where: 
#        vars_yaml_array is the name of the array with the loaded content
#            of the vars.yaml file
#        env is prefix to use for _aws_profile 
#        vpc_name is the vpc to lookup
#        result_name is the variable name that will contain the vpc_id found
#------------------------------------------------------------------------------
function get_aws_vpc_id() {
    local vars_yaml_array=${1}
    local env=${2}
    local vpc_name=${3}
    local result_name=${4}
    local aws_profile=$(get_array_value vars_yaml_array "${env}_aws_profile")
    if [ ! -z ${aws_profile} ]; then
        log "debug" "Looking for AWS vpc_id using profile ${aws_profile}"
        local lcl_aws_vpc_id=$(aws --profile ${aws_profile} ec2 describe-vpcs --filter Name=tag:Name,Values=${vpc_name} --query 'Vpcs[0].VpcId' --output text)
        if [ -z ${lcl_aws_vpc_id} ]; then
        log "error" "Unable to locate vpc_id for Vpc Named: [vpc_name=${vpc_name} aws_profile=${aws_profile}]"
            return -1
        fi
        eval $result_name=\$lcl_aws_vpc_id
        return 0
    fi

    log "error" "Unable to locate an AWS profile in VARS_FILE: [VARS_FILE=${VARS_FILE} vpc_name=${vpc_name}]"
    return -1
}

#------------------------------------------------------------------------------
# Function that searchs a list of files for unprocessed paws keys
# Usage: find_unprocessed_paws_keys [{file_path} ...]. The result
# is a string suitable for storage as a key-value-pair sparse array.
#    where: 
#        file_path is a path to a file to search
#------------------------------------------------------------------------------
function find_unprocessed_paws_keys() {
    awk ' {
        line=$0
        while( match(line, "\\${paws.[a-zA-Z][a-zA-Z0-9]*}") != 0) {
            key=substr(line, RSTART+7, RLENGTH-8)
            keyArray[key]++
            line=substr(line, RSTART+RLENGTH)
        }
    }
    END {
    for(item in keyArray)
        print item "=" | "sort"
    } ' ${@}
}


#------------------------------------------------------------------------------
# Function that process paws keys into their values.
# Usage: process_paws_template_file {key-value-value-array-name} {file-path}
#    where: 
#        key-value-value-array-name is the name of the array where the 
#            the paws key-pair values are stored
#        file-path is a path to a file to process
#------------------------------------------------------------------------------
function process_paws_template_file() {
    for item in $(eval echo \${${1}[@]}); do
        key=${item%%=*}
        value=${item#*=}
        sedcmd='1,$s/${paws.'${key}'}/'${value}'/'
        sed -e $sedcmd ${2} > ${2}.tmp
        mv ${2}.tmp ${2}
    done
}

#------------------------------------------------------------------------------
# Process 'paws' templates if needed
#------------------------------------------------------------------------------
function process_paws_if_needed() {
    if [ ! -f "${VARS_FILE}" ]; then
        if [ -f "${VARS_FILE}.template" ]; then
            cp ${VARS_FILE}.template ${VARS_FILE} 
        fi
    fi
    local DEPLOY_YAML=$(find_file_up_tree "deploy.yml")
    if [ -z "${DEPLOY_YAML}" ]; then
        local template=$(find_file_up_tree "deploy.yml.template")
        if [ -f "${template}" ]; then
            DEPLOY_YAML=${template%.template}
            cp ${template} ${DEPLOY_YAML} 
        fi
    fi
    log "debug" "deploy.yml is at $DEPLOY_YAML"
    local keys_array=($(find_unprocessed_paws_keys $VARS_FILE $DEPLOY_YAML))
    if [ ${#keys_array[@]} -ne 0 ]; then
        log "debug" "about to update paws keys"
        get_array_values_from_user keys_array
        for file in $VARS_FILE $DEPLOY_YAML; do
            process_paws_template_file keys_array $file
        done
    else
        log "debug" "No paws keys to update"
    fi
}

function generate_learn_vars() {
   if [ ! -f $BASE_DIR/learn-vars.yaml -a -f $BASE_DIR/vars.yaml ]; then
     awk '
       BEGIN { IFS=":" }
       /^prod/ { next }
       /^preprod_ec2_key_pair/ { print $1 " learn-" $2; next }
       /^preprod_aws_profile/ { print $1 " learn-" $2; next }
       /^preprod_aws_account/ { print "preprod_aws_account: ${paws.devAwsAccount}"; next }
       { print }
     ' $BASE_DIR/vars.yaml > $BASE_DIR/learn-vars.yaml
     ENV_LIST=${LEARNING_ENV_LIST}
   fi
}

# >>>>>> End of File <<<<<<
