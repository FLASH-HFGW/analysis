"""Generazione dei payload noise per il ciclo di vita esistente di autoreco."""
import json
import os
import shutil
import subprocess
from pathlib import Path


def build_noise_jobs(run_numbers, output_dir, input_path, output_path,
                     analysis_script, reference, iq_sign, request_cpus):
    if reference is None:
        raise ValueError('La modalità noise richiede --noise-reference')
    reference = Path(reference)
    contents = reference.read_bytes()
    doc = json.loads(contents)
    if doc['iq_sign'] != iq_sign:
        raise ValueError('Segno IQ del job (%s) diverso dal riferimento %s (%s)' % (iq_sign, reference, doc['iq_sign']))
    if doc['fs_hz'] != 5e6 or doc['input_range_v'] != 5.0:
        raise ValueError('Il payload noise usa fs=5 MHz e input range +/-5 V')
    module = analysis_script.with_name('iq_noise_statistics.py')
    if not module.is_file():
        raise ValueError('Modulo statistiche non trovato: ' + str(module))
    io_module = analysis_script.with_name('iq_noise_io.py')
    if not io_module.is_file():
        raise ValueError('Modulo I/O non trovato: ' + str(io_module))
    band_module = analysis_script.with_name('analyze_iq_filtered_bands.py')
    if not band_module.is_file():
        raise ValueError('Modulo bande filtrate non trovato: ' + str(band_module))
    for value in (input_path, output_path, str(analysis_script), str(module), str(io_module), str(band_module)):
        if any(c.isspace() for c in value) or any(c in value for c in '\"\'\\,;'):
            raise ValueError('Percorso HTCondor non supportato: ' + value)
    mode_workers = min(3, request_cpus)
    result=[]
    for run in sorted(set(run_numbers)):
        directory=output_dir / ('%05d' % run)
        directory.mkdir(parents=True,exist_ok=True)
        script=directory/'script.sh'
        submit=directory/'submit.sub'
        script.write_text(Path(__file__).with_name('noise_job.sh').read_text())
        script.chmod(0o755)
        (directory/'noise_reference.json').write_bytes(contents)
        transfer=','.join((os.path.relpath(analysis_script,directory),
                           os.path.relpath(module,directory),os.path.relpath(io_module,directory),
                           os.path.relpath(band_module,directory),'noise_reference.json'))
        submit.write_text(f'''executable = script.sh
arguments = {input_path} {run} {output_path} {analysis_script.name} noise_reference.json {iq_sign} {mode_workers}
output = stdout-$(ClusterId).$(ProcID).txt
error = stderr-$(ClusterId).$(ProcID).txt
log = output-$(ClusterId).$(ProcID).log
request_cpus = {request_cpus}
request_memory = 4GB
request_disk = 100GB
transfer_executable = Yes
transfer_input_files = {transfer}
should_transfer_files = Yes
when_to_transfer_output = ON_EXIT
want_io_proxy = true
use_oauth_services = t1
t1_oauth_permissions = profile,email,openid,offline_access
+NoiseProductVersion = "v1"
on_exit_hold = (ExitBySignal == True) || (ExitCode != 0)
queue
''')
        result.append((script,submit))
    return result

def build_iq_v3_jobs(run_numbers, output_dir, input_path, analysis_script,
                     configuration, max_events, request_cpus, product="compact", bin_hz=100, publication=None, attempt=None):
    """Prepare sandbox-only pilot jobs using the existing noise download wrapper."""
    module = analysis_script.with_name("iq_acquisition_metadata.py")
    spectra_module = analysis_script.with_name("iq_compact_spectra.py")
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=analysis_script.parent, text=True
    ).strip()
    wrapper = Path(__file__).with_name("noise_job.sh").read_text()
    result = []
    for run in sorted(set(run_numbers)):
        directory = output_dir / f"{run:05d}"
        directory.mkdir(parents=True, exist_ok=True)
        script, submit = directory / "script.sh", directory / "submit.sub"
        script.write_text(wrapper)
        script.chmod(0o755)
        config = directory / "iq_v3_job.json"
        config.write_text(json.dumps(dict(split_pairs=configuration, max_events=max_events,
                                          product=product, bin_hz=bin_hz, publication=publication)))
        sources = (analysis_script, module, spectra_module)
        if analysis_script.name == "analyze_midas_iq_v3.py":
            sources += tuple(analysis_script.with_name(name) for name in
                             ("iq_thermometers.py", "extract_thermometers.py"))
        if publication:
            sources += (Path(__file__).resolve().with_name("run3_storage.py"),)
            for source in sources:
                target = directory / source.name
                if target.is_symlink():
                    raise ValueError(f"symlink staging target: {target}")
                shutil.copyfile(source, target)
            transfer = [source.name for source in sources] + [config.name]
        else:
            transfer = [os.path.relpath(p, directory) for p in (*sources, config)]
        for value in [input_path, *transfer]:
            if any(not (c.isalnum() or c in "/._-") for c in value):
                raise ValueError("Unsupported HTCondor path: " + value)
        returned = f"run{run:05d}_job_status.json"
        if publication:
            returned += ",publication.json"
        else:
            returned += f",run{run:05d}_iq_v3.h5"
        tag = f'+FlashRun3Attempt = "{attempt}"\n' if attempt else ""
        submit.write_text(f"""executable = script.sh
arguments = {input_path} {run} pilot {analysis_script.name} {config.name} {commit} {request_cpus}
output = stdout-$(ClusterId).$(ProcID).txt
error = stderr-$(ClusterId).$(ProcID).txt
log = output-$(ClusterId).$(ProcID).log
request_cpus = {request_cpus}
request_memory = 4GB
request_disk = 100GB
transfer_executable = YES
should_transfer_files = YES
when_to_transfer_output = ON_EXIT
transfer_output_files = {returned}
transfer_input_files = {','.join(transfer)}
want_io_proxy = true
use_oauth_services = t1
t1_oauth_permissions = profile,email,openid,offline_access
on_exit_hold = (ExitBySignal == True) || (ExitCode != 0)
{tag}queue
""")
        result.append((script, submit))
    return result


def check_run3_inputs(submit):
    """Check the exact paths Condor will spool from the local submit directory."""
    attributes = dict(line.split(" = ", 1) for line in submit.read_text().splitlines()
                      if " = " in line)
    paths = [attributes["executable"], *attributes["transfer_input_files"].split(",")]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate Run3 transfer input")
    for name in paths:
        path = submit.parent / name
        if Path(name).name != name or path.is_symlink() or not path.is_file():
            raise ValueError(f"invalid staged Run3 input: {path}")
        with path.open("rb") as stream:
            if not stream.read(1):
                raise ValueError(f"empty staged Run3 input: {path}")
