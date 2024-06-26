"""
HTTP/2 Connection
"""
import socket
from threading import Thread
import scapy.contrib.http2 as h2
from scapy.all import hex_bytes
from . import h2_frames, utils
import socks
import datetime


class H2Connection:
    def __init__(self, hostname, port_number, read_timeout=3, proxy_hostname=None, proxy_port_number=None):
        self.hostname = hostname  # e.g http2.github.io
        self.port_number = port_number  # e.g 443
        self.proxy_hostname = proxy_hostname  # proxy hostname e.g 127.0.0.1
        self.proxy_port_number = proxy_port_number  # proxy port e.g 10808
        self.raw_socket = None  # raw socket object
        self.read_timeout = read_timeout  # timeout when reading response from socket
        self.last_used_stream_id = 1  # define last stream ID used to continue stream IDs
        self.is_connection_closed = True  # if connection is not closed, this variable is False
        # HTTP/2 Connection Preface
        self.H2_PREFACE = hex_bytes('505249202a20485454502f322e300d0a0d0a534d0d0a0d0a')
        self.DEFAULT_SETTINGS = {
            'SETTINGS_HEADER_TABLE_SIZE': {
                'id': 1,
                'value': 4096
            },
            'SETTINGS_ENABLE_PUSH': {
                'id': 2,
                'value': 0
            },
            'SETTINGS_MAX_CONCURRENT_STREAMS': {
                'id': 3,
                'value': 100
            },
            'SETTINGS_INITIAL_WINDOW_SIZE': {
                'id': 4,
                'value': 65535
            },
            'SETTINGS_MAX_FRAME_SIZE': {
                'id': 5,
                'value': 16384
            },
            'SETTINGS_MAX_HEADER_LIST_SIZE': {
                'id': 6,
                'value': None
            },
        }

    def setup_connection(self):
        """
        TODO
        :return:
        """
        try:
            self._create_raw_socket()
            self._send_h2_connection_preface()  # send HTTP/2 Connection Preface
            self._send_client_initial_settings_frame()  # send client initial settings frame to server
        except Exception as e:
            print('# Error in setting the connection up : ' + str(e))
            exit(1)

        else:
            self.is_connection_closed = False


    def __thread_response_frame_parsing(self, _timeout=0.5):
        """
        method which is thread oriented for response parsing
        :param _timeout:
        :return:
        """
        try:
            while not self.is_connection_closed:
                resp = self.read_response_from_socket(_timeout=_timeout)
                if resp:
                    self.old_parse_frames_bytes(resp)

        except KeyboardInterrupt:
            exit()

    def start_thread_response_parsing(self, _timeout=0.5):
        try:
            Thread(target=self.__thread_response_frame_parsing, args=(_timeout,)).start()
        except KeyboardInterrupt:
            exit()

    def _create_socks_socket(self):
        """
        create a SOCKS5 Socket with self.proxy_hostname and self.proxy_port_number
        set the self.raw_socket to created SOCKS5
        :return:
        """

        socks.set_default_proxy(socks.SOCKS5, self.proxy_hostname, self.proxy_port_number)
        socket.socket = socks.socksocket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 0)
        sock.connect((self.hostname, self.port_number))
        self.raw_socket = sock
        sock_addr = sock.getsockname()
        print(f'+ Connected through Proxy: {self.hostname}:{self.port_number} --> {sock_addr[0]}:{sock_addr[1]}')

    def _create_raw_socket(self):
        """
        create raw socket and return it
        :return:
        """

        if self.proxy_hostname:
            self._create_socks_socket()
            return

        raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Enable Nagle algorithm
        raw_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 0)
        raw_socket.connect((self.hostname, self.port_number))

        self.raw_socket = raw_socket
        sock_addr = raw_socket.getsockname()
        print(f'+ Connected to: {self.hostname}:{self.port_number} --> {sock_addr[0]}:{sock_addr[1]}')

    def _send_h2_connection_preface(self):
        self.send_bytes(self.H2_PREFACE)
        print('+ H2 connection preface sent')

    def get_using_socket(self):
        """
        get using socket. for example return raw_socket
        :return:
        """
        return self.raw_socket

    def send_bytes(self, bytes_data: bytes):
        """
        send bytes into socket(raw or TLS socket)
        :param bytes_data: bytes data for sending into socket
        :return:
        """
        using_socket = self.get_using_socket()
        try:
            sending_request_time = datetime.datetime.now()
            using_socket.send(bytes_data)
            return sending_request_time
        except Exception as e:
            print('# Error in sending bytes: ' + str(e))

    def send_frames(self, frames):
        """
        send frames into socket(raw or TLS socket)
        :param frames: frame for sending into socket
        :return:
        """
        using_socket = self.get_using_socket()
        self.send_bytes(bytes(frames))

    def read_response_from_socket(self, _timeout=None) -> bytes:
        """
        read from socket(raw or TLS socket), and return bytes
        :return:
        """

        if _timeout is None:
            timeout = self.read_timeout
        else:
            timeout = _timeout

        using_socket = self.get_using_socket()
        try:
            using_socket.settimeout(timeout)

        except Exception as e:
            return b''

        response = b''
        # time_received_response = []
        while True:
            try:
                data = using_socket.recv(4096)
                # receiving_time = datetime.datetime.now()
                if not data:
                    break
            except socket.timeout:
                break
            response += data
        #     http2 = h2.H2Seq(data)
        #     headers_and_no_data = False
        #     for frame in http2.frames:
        #         if hasattr(frame, 'flags'):
        #             flags = frame.flags
        #             print(frame.flags)
        #             if 'ES' in frame.flags:
        #                 headers_and_no_data = False
        #                 time_received_response.append(receiving_time)
        #             elif 'EH' in frame.flags:
        #                 if headers_and_no_data:
        #                     time_received_response.append(saved_time)
        #                 saved_time = receiving_time
        #                 headers_and_no_data = True
        #         else:
        #             flags = []
        #     if 'EH' in flags:
        #         time_received_response.append(saved_time)
        # return response, time_received_response
        return response

    def old_parse_frames_bytes(self, frame_bytes, is_verbose=False):
        """
        parse frames bytes. for example parse response frames from server
        :param frame_bytes: bytes type of frames
        :param is_verbose: if is_verbose is True, then the method of .show() will be invoked for the frame
        :return:
        """

        h2_frames.parse_response_frames_bytes(frame_bytes, socket_obj=self.get_using_socket(), is_verbose=is_verbose)

    def send_ping_frame(
            self,
            ping_data="12345678"
    ):
        """
        send ping frame to make the idle connection active
        :param ping_data:
        :return:
        """
        ping_frame = h2_frames.create_ping_frame(ping_data=ping_data)
        self.send_bytes(bytes(ping_frame))

    def close_connection(self):
        """
        close the connection
        :return:
        """
        go_away_frame = h2_frames.create_go_away_frame(err_code=0)
        self.send_bytes(bytes(go_away_frame))
        self.raw_socket.close()
        self.raw_socket = None
        self.is_connection_closed = True

    def _send_client_initial_settings_frame(self):
        """
        send client initial settings to the server
        :return:
        """

        settings_list = []
        for s in self.DEFAULT_SETTINGS.keys():
            if self.DEFAULT_SETTINGS[s]['value'] is None:  # if value of the setting is None, then do not send it
                continue
            temp_s = h2.H2Setting(id=self.DEFAULT_SETTINGS[s]['id'], value=self.DEFAULT_SETTINGS[s]['value'])
            settings_list.append(temp_s)

        client_initial_settings_frame = h2_frames.create_settings_frame(settings=settings_list)

        self.send_bytes(bytes(client_initial_settings_frame))
        print('+ Client initial SETTINGS frame sent: ')
        print('// Client SETTINGS //')
        print(self.DEFAULT_SETTINGS)
        print()

    def generate_stream_ids(self, number_of_streams):
        """
        generate stream IDs by checking self.last_used_stream_id (incremental) just odd stream IDs
        :param number_of_streams:
        :return:
        """

        if not isinstance(number_of_streams, int) or number_of_streams <= 0:
            print(f"The number of streams passed to the function generate_stream_ids is: {number_of_streams}")
            raise ValueError("number_of_streams must be a positive integer")

        if self.last_used_stream_id % 2 == 0:
            self.last_used_stream_id += 1

        start_stream_id = self.last_used_stream_id + 2
        end_stream_id = (number_of_streams * 2) + start_stream_id
        stream_ids_list = []

        if end_stream_id <= start_stream_id:
            raise ValueError("There's a problem with the stream_id range. Please check the number_of_streams value.")

        for i in range(start_stream_id, end_stream_id, 2):
            stream_ids_list.append(i)

        self.last_used_stream_id = stream_ids_list[-1]
        return stream_ids_list

    def create_single_packet_http2_request_frames(
            self,
            authority,
            scheme,
            path,
            headers_string,
            stream_id,
            body,
            check_headers_lowercase=True,
            method='POST'
    ):
        """
        create simple http/2 POST request(Headers Frame + Data)
        this function returns two variable, the first return variable is the request with body without the last byte,
        and the second return variable is last frame with last byte
        :param method: method of the request. e.g. GET
        :param authority: equivalent of host header in http/1. e.g. google.com
        :param scheme: http or https
        :param path: request path. e.g. /index.html
        :param headers_string: headers in request. split with \n --> user-agent: xxx\n
        :param check_headers_lowercase: if this is True, the headers names will be checked to be lowercase
        :param stream_id: stream id of the request
        :param body: if the request method is not get, then it needs to have body
        :return:
        """
        if body:
            body = bytes(body, 'utf-8')

        if check_headers_lowercase:
            headers_string = utils.make_header_names_small(headers_string)


        request_frames = h2_frames.create_headers_frame(
            method=method,
            authority=authority,
            scheme=scheme,
            path=path,
            headers_string=headers_string,
            stream_id=stream_id,
            body=body, #body is by default None in this function
        )

        if body != None:
            # save in last_byte the last byte of the last frame of the request
            last_byte = request_frames.frames[-1].data[-1:]
            # remove the last byte of data from the last frame of the request
            request_frames.frames[-1].data = request_frames.frames[-1].data[:-1]
            # remove the end stream flag from the last frame of the request
            request_frames.frames[-1].flags.remove('ES')
            # create a new data frame with the last byte of the last frame of the request and the end stream flag set
            new_data_frame = h2.H2Frame(stream_id=stream_id, flags={'ES'}) / h2.H2DataFrame(data=last_byte)
        else: #if body is None (GET requests for example)
            # TODO: See the commented method below and it's TODOs to see if it's necessary to use the Content Length header with value 1 and send a data frame with 1 casual byte of body (one casual letter)
            # and try to understand why the ES flag is removed from the first frame of the request and not from the last in his TODOs.
            request_frames.frames[-1].flags.remove('ES')
            #request_frames.frames[-1].flags.remove('EH')
            new_data_frame = h2.H2Frame(stream_id=stream_id, flags={'ES'}) / h2.H2DataFrame(data=b'')
            #continuation_frame = h2.H2Frame(stream_id=stream_id, flags={'EH'}) / h2.H2ContinuationFrame() #EH = End Headers

        return request_frames, new_data_frame

    # def create_single_packet_http2_get_request_frames(
    #         self,
    #         authority,
    #         scheme,
    #         path,
    #         headers_string,
    #         stream_id,
    #         check_headers_lowercase=True,
    #         body=None,
    #         method='GET',
    # ):
    #     """
    #     create simple http/2 GET request(Headers Frame + Null Data)
    #     this function returns two variable, the first return variable is the request with body without the last byte,
    #     and the second return variable is last frame with last byte
    #     :param method: method of the request. e.g. GET
    #     :param authority: equivalent of host header in http/1. e.g. google.com
    #     :param scheme: http or https
    #     :param path: request path. e.g. /index.html
    #     :param headers_string: headers in request. split with \n --> user-agent: xxx\n
    #     :param check_headers_lowercase: if this is True, the headers names will be checked to be lowercase
    #     :param stream_id: stream id of the request
    #     :param body: if the request method is not get, then it needs to have body
    #     :return:
    #     """
    #     if body:
    #         body = bytes(body, 'utf-8')

    #     if check_headers_lowercase:
    #         headers_string = utils.make_header_names_small(headers_string)

    #     # TODO: implement content-length: 1 method
    #     # headers_string = headers_string.strip()
    #     # headers_string += '\ncontent-length: 1\n'

    #     headers_string = utils.make_header_names_small(headers_string)

    #     get_request_frames = sh2_frames.create_headers_frame(
    #         method=method,
    #         authority=authority,
    #         scheme=scheme,
    #         path=path,
    #         headers_string=headers_string,
    #         stream_id=stream_id,
    #         body=None,
    #     )
    #     # TODO
    #     # get_request_frames.frames[0].flags.remove('ES')
    #     # continuation_frame = h2.H2Frame(stream_id=stream_id, flags={'EH'}) / h2.H2ContinuationFrame() #EH = End Headers
    #     # new_data_frame = h2.H2Frame(stream_id=stream_id, flags={'ES'}) / h2.H2DataFrame(data=b'A')

    #     return get_request_frames

    def create_simple_http2_request(
            self,
            method,
            authority,
            scheme,
            path,
            headers_string,
            stream_id,
            body=None,
            check_headers_lowercase=True,
    ):
        """
        create simple http/2 request(Headers Frame + Data(Optional)) and return the frames
        :param method: method of the request. e.g. GET
        :param authority: equivalent of host header in http/1. e.g. google.com
        :param scheme: http or https
        :param path: request path. e.g. /index.html
        :param headers_string: headers in request. split with \n --> user-agent: xxx\n
        :param stream_id: stream id of the request
        :param body: if the request method is not get, then it needs to have body
        :param check_headers_lowercase:  if this is True, the headers names will be checked to be lowercase
        :return:
        """

        if body:
            body = bytes(body, 'utf-8')

        if check_headers_lowercase:
            headers_string = utils.make_header_names_small(headers_string)

        request_frames = h2_frames.create_headers_frame(
            method=method,
            authority=authority,
            scheme=scheme,
            path=path,
            headers_string=headers_string,
            stream_id=stream_id,
            body=body,
        )

        return request_frames

    def send_simple_http2_request(
            self,
            method,
            authority,
            scheme,
            path,
            headers_string,
            stream_id,
            body=None,
            check_headers_lowercase=True,
    ):
        """
        send simple http/2 request(Headers Frame + Data(Optional))
        :param method: method of the request. e.g. GET
        :param authority: equivalent of host header in http/1. e.g. google.com
        :param scheme: http or https
        :param path: request path. e.g. /index.html
        :param headers_string: headers in request. split with \n --> user-agent: xxx\n
        :param stream_id: stream id of the request
        :param body: if the request method is not get, then it needs to have body
        :param check_headers_lowercase:  if this is True, the headers names will be checked to be lowercase
        :return:
        """

        if body:
            body_bytes = bytes(body, 'utf-8')

        if check_headers_lowercase:
            headers_string = utils.make_header_names_small(headers_string)

        request_frames = h2_frames.create_headers_frame(
            method=method,
            authority=authority,
            scheme=scheme,
            path=path,
            headers_string=headers_string,
            stream_id=stream_id,
            body=body_bytes,
        )

        self.send_bytes(bytes(request_frames))
        # print('Headers Request Frame Sent: ' + str(request_frames))
        more_info_msg = f"""+----- Start Request Info -----+
Stream ID: {stream_id}
:method: {method}
:authority: {authority}
:scheme: {scheme}
:path: {path}
{headers_string}
body:
{body}
+----- END Request Info -----+
"""
        print(more_info_msg)
