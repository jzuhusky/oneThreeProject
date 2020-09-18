def decodeEmail(encodedString):
    """Sometimes SMILES formulas have @'s in them and
    Cloudfare returns these to us as "obfuscated emails", so we have to hack around
    this to decode the string that's a part of the smiles formula we want to pull.
    This function does just that given the encrypted "email".
    """
    # https://usamaejaz.com/cloudflare-email-decoding/
    r = int(encodedString[:2], 16)
    email = "".join(
        [
            chr(int(encodedString[i : i + 2], 16) ^ r)
            for i in range(2, len(encodedString), 2)
        ]
    )
    return email
