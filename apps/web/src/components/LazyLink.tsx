import NextLink from "next/link";
import type {ComponentProps} from "react";

type LazyLinkProps = ComponentProps<typeof NextLink>;

export function LazyLink(props:LazyLinkProps){return <NextLink {...props}/>}
