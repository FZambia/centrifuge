from adjacent import get_connection_parameters


def main(request):

    params = get_connection_parameters(request.user)

    return dict(
        CENTRIFUGE_URL=params['url'],
        CENTRIFUGE_USER=params['user'],
        CENTRIFUGE_PROJECT=params['project'],
        CENTRIFUGE_TIMESTAMP=params['timestamp'],
        CENTRIFUGE_TOKEN=params['token']
    )
