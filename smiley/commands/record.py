import logging
import os

from smiley import db
from smiley.commands import listen_cmd


class Record(listen_cmd.ListeningCommand):
    """Listen for running programs and record the data to a database for
    later use.

    """

    log = logging.getLogger(__name__)

    _cwd = None

    def get_parser(self, prog_name):
        parser = super(Record, self).get_parser(prog_name)
        parser.add_argument(
            '--database',
            default='smiley.db',
            help='filename for the database (%(default)s)',
        )
        return parser

    def _process_message(self, msg):
        msg_type, msg_payload = msg
        self.log.debug('MESSAGE: %s %r', msg_type, msg_payload)

        if msg_type == 'start_run':
            command_line = ' '.join(msg_payload.get('command_line', []))
            self.log.info(
                'Starting new run: %s',
                command_line,
            )
            self._cached_files = set()
            self._cwd = msg_payload.get('cwd', '')
            if self._cwd:
                self._cwd = self._cwd.rstrip(os.sep) + os.sep
            self.db.start_run(
                run_id=msg_payload['run_id'],
                cwd=self._cwd,
                description=msg_payload.get('command_line', []),
                start_time=msg_payload.get('timestamp'),
            )

        elif msg_type == 'end_run':
            self.log.info('Finished run')
            self.db.end_run(
                run_id=msg_payload['run_id'],
                end_time=msg_payload.get('timestamp'),
                message=msg_payload.get('message'),
                traceback=msg_payload.get('traceback'),
            )

        else:
            self.db.trace(
                run_id=msg_payload['run_id'],
                call_id=msg_payload['call_id'],
                event=msg_type,
                func_name=msg_payload.get('func_name'),
                line_no=msg_payload.get('line_no'),
                filename=msg_payload.get('filename'),
                trace_arg=msg_payload.get('arg'),
                local_vars=msg_payload.get('local_vars'),
                timestamp=msg_payload.get('timestamp'),
            )

        filename = msg_payload.get('filename')
        if filename and filename not in self._cached_files:
            # Should we be decoding the text file here?
            with open(filename, 'rb') as f:
                body = f.read()
            self.db.cache_file_for_run(
                msg_payload['run_id'],
                msg_payload['filename'],
                body,
            )
            # Track the files we have cached so we do not need to
            # re-cache them for the same run.
            self._cached_files.add(msg_payload['filename'])

    def take_action(self, parsed_args):
        self.db = db.DB(parsed_args.database)
        self._cached_files = set()
        return super(Record, self).take_action(parsed_args)
